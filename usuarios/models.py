import uuid

from django.db import models

# Importa Usuario do app contas, pois Paciente e Terapeuta são perfis
# construídos em cima de um Usuario já existente.
from contas.models import Usuario


# ENUMS
class GeneroChoices(models.TextChoices):
    """
    Opções de gênero para o campo genero de paciente
    usando textchoices
    """
    MASCULINO = "masculino", "Masculino"
    FEMININO  = "feminino",  "Feminino"
    OUTRO     = "outro",     "Outro"


class StatusVinculo(models.TextChoices):
    """
    Ciclo de vida de um vínculo entre paciente e terapeuta:
      pendente  → terapeuta ainda não respondeu o convite
      recusado  → terapeuta recusou
      ativo     → vínculo aceito e em andamento
      encerrado → vínculo foi finalizado
    """
    PENDENTE  = "pendente",  "Pendente"
    RECUSADO  = "recusado",  "Recusado"
    ATIVO     = "ativo",     "Ativo"
    ENCERRADO = "encerrado", "Encerrado"


# MODELS
class Paciente(models.Model):
    """
    Perfil clínico do paciente.
    Não duplicamos nome/email aqui — esses dados já estão em Usuario.
    Paciente guarda apenas o que é específico do contexto clínico.
    """

    class Meta:
        # nome exato da tabela no banco de dados
        db_table = "paciente"
        # esses nomes aparecem no painel admin do Django
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"


    # UUID como chave primária
    # O uuid.uuid4 gera um valor aleatório a cada novo registro.
    # editable=False impede que o campo apareça em formulários, ele é gerado automaticamente.
    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # OneToOneField → um Usuario só pode ter um perfil de Paciente.
    # Se o Usuario for deletado (on_delete=RESTRICT), o banco bloqueia a operação
    # enquanto existir um Paciente vinculado — evita perda acidental de dados clínicos.
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.RESTRICT,
        related_name="paciente",  # acesso inverso: usuario.paciente
        db_column="usuario_id",
    )

    # DateField → apenas a data de nascimento, sem horário
    data_nascimento = models.DateField()

    genero = models.CharField(
        max_length=20,
        choices=GeneroChoices.choices,
    )

    # Observações clínicas livres sobre o paciente, sem tamanho fixo
    observacoes = models.TextField(null=True, blank=True)

    # auto_now_add=True → preenche automaticamente com a data/hora atual só na criação
    criado_em = models.DateTimeField(auto_now_add=True)

    # auto_now=True → atualiza automaticamente para a data/hora atual em todo save()
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Paciente: {self.usuario.nome}"


class Terapeuta(models.Model):
    """
    Perfil profissional do terapeuta.
    Assim como Paciente, estende Usuario com dados específicos da área clínica.
    """

    class Meta:
        db_table = "terapeuta"
        verbose_name = "Terapeuta"
        verbose_name_plural = "Terapeutas"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.RESTRICT,
        related_name="terapeuta",  # acesso inverso: usuario.terapeuta
        db_column="usuario_id",
    )

    # Especialidade clínica do terapeuta (ex: "Psicologia Cognitiva", "Psicanálise")
    especialidade = models.CharField(max_length=255)

    # Bio pública — aparece para pacientes na busca de terapeutas
    bio = models.TextField(null=True, blank=True)

    # ativo=False pode ser usado para desabilitar o terapeuta sem deletar seus dados
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Terapeuta: {self.usuario.nome} ({self.especialidade})"


class Vinculo(models.Model):
    """
    Representa a relação terapêutica entre um Paciente e um Terapeuta.
    É por meio do Vínculo que o terapeuta ganha acesso aos dados do paciente
    (diário, autotestes, prontuário etc).
    Um paciente pode ter vínculo com mais de um terapeuta ao longo do tempo.
    """

    class Meta:
        db_table = "vinculo"
        verbose_name = "Vínculo"
        verbose_name_plural = "Vínculos"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # ForeignKey (não OneToOne) → um paciente pode ter vários vínculos ao longo do tempo
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.RESTRICT,
        related_name="vinculos",  # acesso: paciente.vinculos.all()
        db_column="paciente_id",
    )

    terapeuta = models.ForeignKey(
        Terapeuta,
        on_delete=models.RESTRICT,
        related_name="vinculos",  # acesso: terapeuta.vinculos.all()
        db_column="terapeuta_id",
    )

    # Status começa como pendente — o paciente precisa aceitar o vínculo
    status = models.CharField(
        max_length=20,
        choices=StatusVinculo.choices,
        default=StatusVinculo.PENDENTE,
    )

    iniciado_em = models.DateTimeField(auto_now_add=True)

    # null=True → preenchido apenas quando o vínculo for encerrado
    encerrado_em = models.DateTimeField(null=True, blank=True)

    # Razão do encerramento — preenchido pelo terapeuta ou pelo sistema
    motivo_encerramento = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.paciente.usuario.nome} ↔ {self.terapeuta.usuario.nome} [{self.status}]"


class Consentimento(models.Model):
    """
    Registro de consentimento do paciente para que o terapeuta acesse seus dados.
    Exigido pela LGPD — sem consentimento registrado, o terapeuta não pode
    visualizar informações sensíveis como diário e autotestes.
    """

    class Meta:
        db_table = "consentimento"
        verbose_name = "Consentimento"
        verbose_name_plural = "Consentimentos"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="consentimentos",
        db_column="paciente_id",
    )

    terapeuta = models.ForeignKey(
        Terapeuta,
        on_delete=models.CASCADE,
        related_name="consentimentos",
        db_column="terapeuta_id",
    )

    # aceito=False → consentimento criado mas ainda não confirmado pelo paciente
    # aceito=True  → paciente confirmou e data_aceita foi preenchida
    aceito = models.BooleanField(default=False)

    # Preenchido automaticamente quando o paciente aceitar, null enquanto pendente
    data_aceita = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        status = "aceito" if self.aceito else "pendente"
        return f"Consentimento {status} — {self.paciente.usuario.nome} → {self.terapeuta.usuario.nome}"


class PreferenciasPrivacidade(models.Model):
    """
    Controle do paciente sobre quais dados ele permite compartilhar com o terapeuta.
    Mesmo com consentimento ativo, o paciente pode escolher ocultar
    o diário ou os autotestes individualmente.
    """

    class Meta:
        db_table = "preferencias_privacidade"
        verbose_name = "Preferências de Privacidade"
        verbose_name_plural = "Preferências de Privacidade"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # OneToOneField → cada paciente tem exatamente um registro de preferências
    paciente = models.OneToOneField(
        Paciente,
        on_delete=models.CASCADE,
        related_name="preferencias_privacidade",  # acesso: paciente.preferencias_privacidade
        db_column="paciente_id",
        null=True,
        blank=True,
    )

    # Se False → o terapeuta não pode ler as entradas do diário do paciente
    compartilhar_diario = models.BooleanField(null=True, blank=True)

    # Se False → o terapeuta não pode ver os resultados dos autotestes
    compartilhar_autotestes = models.BooleanField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Privacidade de {self.paciente.usuario.nome}"