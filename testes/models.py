import uuid

from django.db import models

# Importa Paciente do app usuarios pois AplicacaoTeste precisa saber
# qual paciente realizou o teste.
from usuarios.models import Paciente


# ENUMS
class ClassificacaoChoices(models.TextChoices):
    """
    Estado atual de uma aplicação de teste:
      a fazer      → paciente ainda não fez  
      em_andamento → paciente começou mas ainda não terminou
      concluido    → paciente respondeu todas as questões
      cancelado    → teste foi interrompido antes de terminar
    """
    A_FAZER = "a fazer", "a fazer"
    EM_ANDAMENTO = "em andamento", "Em andamento"
    CONCLUIDO    = "concluido",    "Concluído"
    CANCELADO    = "cancelado",    "Cancelado"



# MODELS
class Autoteste(models.Model):
    """
    Define um questionário disponível na plataforma.
    É um template — não está vinculado a nenhum paciente específico.
    Exemplos: PHQ-9 (depressão), GAD-7 (ansiedade), etc.
    Um Autoteste pode ser aplicado para muitos pacientes via AplicacaoTeste.
    """

    class Meta:
        # nome exato da tabela no banco de dados
        db_table = "autoteste"
        # esses nomes aparecem no painel admin do Django
        verbose_name = "Autoteste"
        verbose_name_plural = "Autotestes"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    nome = models.CharField(max_length=255)

    descricao = models.TextField(null=True, blank=True)

    # ativo=False permite desabilitar um teste sem deletá-lo,
    # preservando o histórico de quem já o realizou
    ativo = models.BooleanField(default=True)

    # auto_now_add=True → preenche automaticamente com a data/hora atual só na criação
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.nome


class Questao(models.Model):
    """
    Representa uma pergunta dentro de um Autoteste.
    As respostas são sempre em escala numérica (ex: 1 a 5),
    o que facilita o cálculo do score final da aplicação.
    Um Autoteste tem várias Questões (ForeignKey).
    """

    class Meta:
        db_table = "questao"
        verbose_name = "Questão"
        verbose_name_plural = "Questões"
        # Garante que a ordem de exibição seja única por autoteste,
        # não podem existir duas questões com a mesma posição no mesmo teste
        constraints = [
            models.UniqueConstraint(
                fields=["autoteste", "ordem_exibicao"],
                name="uq_questao_autoteste_ordem",
            )
        ]
        # Ordena as questões pela ordem de exibição por padrão
        ordering = ["ordem_exibicao"]

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # ForeignKey → um Autoteste tem várias Questões
    # on_delete=DO_NOTHING → alinhado com o schema original (no action)
    autoteste = models.ForeignKey(
        Autoteste,
        on_delete=models.DO_NOTHING,
        related_name="questoes",  # acesso: autoteste.questoes.all()
        db_column="autoteste_id",
    )

    # Texto da pergunta exibida ao paciente
    enunciado = models.TextField()

    # Define a posição da questão no questionário (1ª, 2ª, 3ª pergunta...)
    # null=True → ordem opcional, mas recomendado sempre preencher
    ordem_exibicao = models.IntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"[{self.autoteste.nome}] Q{self.ordem_exibicao}: {self.enunciado[:50]}"


class AplicacaoTeste(models.Model):
    """
    Representa uma sessão de teste de um paciente específico.
    É o "histórico", cada vez que um paciente realiza um Autoteste,
    um registro de AplicacaoTeste é criado.
    Ex: João realizou o PHQ-9 em 01/06/2025 e obteve score 12.
    """

    class Meta:
        db_table = "aplicacao_teste"
        verbose_name = "Aplicação de Teste"
        verbose_name_plural = "Aplicações de Teste"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.DO_NOTHING,
        related_name="aplicacoes_teste",  # acesso: paciente.aplicacoes_teste.all()
        db_column="id_paciente",
    )

    # Qual autoteste foi aplicado
    autoteste = models.ForeignKey(
        Autoteste,
        on_delete=models.DO_NOTHING,
        related_name="aplicacoes",  # acesso: autoteste.aplicacoes.all()
        db_column="auto_teste_id",
    )

    # Score calculado ao final do teste somando os valores das respostas.
    # null=True → ainda não calculado (teste em andamento)
    score = models.IntegerField(null=True, blank=True)

    # Estado atual da aplicação — começa em_andamento e vai para concluido ou cancelado
    classificacao = models.CharField(
        max_length=20,
        choices=ClassificacaoChoices.choices,
        default=ClassificacaoChoices.A_FAZER,
    )

    # Data em que o paciente concluiu o teste, null enquanto em andamento
    data_realizada = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        nome_teste = self.autoteste.nome if self.autoteste else "teste removido"
        nome_paciente = self.paciente.usuario.nome if self.paciente else "paciente removido"
        return f"{nome_paciente} — {nome_teste} [{self.classificacao}]"


class RespostaQuestao(models.Model):
    """
    Armazena a resposta de um paciente para uma questão específica
    dentro de uma AplicacaoTeste.
    É o nível mais especifico do sistema de testes, cada linha representa
    a resposta de uma questão em uma sessão de teste.
    O score final da AplicacaoTeste é calculado somando os valor_resposta
    de todas as RespostaQuestao daquela aplicação.
    """

    class Meta:
        db_table = "resposta_questao"
        verbose_name = "Resposta de Questão"
        verbose_name_plural = "Respostas de Questões"
        indexes = [
            # Índice para acelerar buscas por questão, ex: "quantas pessoas
            # responderam X nessa questão?"
            models.Index(fields=["questao"], name="idx_resposta_questao"),
        ]

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # Qual sessão de teste essa resposta pertence
    aplicacao_teste = models.ForeignKey(
        AplicacaoTeste,
        on_delete=models.DO_NOTHING,
        related_name="respostas",  # acesso: aplicacao.respostas.all()
        db_column="aplicacao_teste_id",
    )

    # Qual questão foi respondida
    questao = models.ForeignKey(
        Questao,
        on_delete=models.DO_NOTHING,
        related_name="respostas",  # acesso: questao.respostas.all()
        db_column="questao_id",
    )

    # Valor numérico escolhido pelo paciente na escala (ex: 1, 2, 3, 4 ou 5)
    # null=True → questão ainda não respondida
    valor_resposta = models.IntegerField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Resposta {self.valor_resposta} — Questão {self.questao_id}"