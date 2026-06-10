import uuid

from django.db import models

# Importamos Paciente do app usuarios pois o diário pertence a um paciente específico
from usuarios.models import Paciente


# ENUMS
class HumorChoices(models.TextChoices):
    """
    Escala de humor registrada pelo paciente ao criar uma entrada no diário.
    Vai de muito_triste até muito_feliz, 5 níveis para facilitar
    a visualização de tendências emocionais ao longo do tempo
    """
    MUITO_TRISTE = "muito_triste", "Muito Triste"
    TRISTE       = "triste",       "Triste"
    NEUTRO       = "neutro",       "Neutro"
    FELIZ        = "feliz",        "Feliz"
    MUITO_FELIZ  = "muito_feliz",  "Muito Feliz"


# MODEL
class Diario(models.Model):
    """
    Representa uma entrada no diário emocional do paciente.
    O paciente pode escrever livremente sobre como está se sentindo
    e registrar seu humor do dia.
    Essas entradas podem ser compartilhadas com o terapeuta dependendo
    das preferências de privacidade do paciente (tabela PreferenciasPrivacidade).
    Também podem ser analisadas pela IA (tabela AnaliseIa) para identificar
    padrões emocionais e gerar alertas clínicos.
    """

    class Meta:
        # nome exato da tabela no banco de dados
        db_table = "diario"
        # esses nomes aparecem no painel admin do Django
        verbose_name = "Diário"
        verbose_name_plural = "Diários"
        # Ordena as entradas da mais recente para a mais antiga por padrão
        ordering = ["-criado_em"]
        indexes = [
            # Índice para acelerar buscas por paciente
            # ex: "buscar todas as entradas do diário do paciente X"
            models.Index(fields=["paciente"], name="idx_diario_paciente"),
        ]

    # UUID como chave primária
    # O uuid.uuid4 gera um valor aleatório a cada novo registro.
    # editable=False impede que o campo apareça em formulários, ele é gerado automaticamente.
    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # ForeignKey → um Paciente pode ter muitas entradas no diário
    # on_delete=RESTRICT → bloqueia a exclusão do Paciente enquanto
    # houver entradas no diário, protegendo o histórico clínico
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.RESTRICT,
        related_name="entradas_diario",  # acesso: paciente.entradas_diario.all()
        db_column="paciente_id",
    )

    # Título opcional da entrada, o paciente pode deixar em branco
    titulo = models.CharField(max_length=255, null=True, blank=True)

    conteudo = models.TextField()

    # Humor registrado pelo paciente no momento da escrita
    # null=True → o paciente pode optar por não registrar o humor
    humor = models.CharField(
        max_length=20,
        choices=HumorChoices.choices,
        null=True,
        blank=True,
    )

    # auto_now_add=True → preenche automaticamente com a data/hora atual só na criação
    criado_em = models.DateTimeField(auto_now_add=True)
    # auto_now=True → atualiza automaticamente para a data/hora atual em todo save()
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        titulo = self.titulo or "Sem título"
        return f"[{self.paciente.usuario.nome}] {titulo} — {self.criado_em:%d/%m/%Y}"