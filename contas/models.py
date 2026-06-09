import uuid

# make_password transforma a senha digitada pelo usuário em um hash seguro.
from django.contrib.auth.hashers import make_password
from django.db import models


class Usuario(models.Model):
    """
    Tabela central de contas. Todo mundo que usa o sistema
    (paciente, terapeuta, administrador) tem um registro aqui.
    Os perfis específicos ficam em tabelas separadas apontando para esta.
    """

    class Meta:
        # nome exato da tabela no banco de dados
        db_table = "usuario"
        # esses nomes aparecem no painel admin do Django
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    # UUID como chave primária
    # O uuid.uuid4 gera um valor aleatório a cada novo registro.
    # editable=False impede que o campo apareça em formulários, ele é gerado automaticamente.
    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    nome = models.CharField(max_length=255)

    # EmailField valida o formato do email automaticamente
    # unique=True impede dois usuários com o mesmo email
    # db_index=True cria um índice no banco, tornando buscas por email muito mais rápidas
    email = models.EmailField(max_length=255, unique=True, db_index=True)

    # nunca salvamos a senha pura aqui, apenas o hash gerado pelo método set_senha()
    senha_hash = models.TextField()

    # null=True  → permite NULL no banco de dados
    # blank=True → permite campo vazio em formulários Django
    # Ambos juntos = campo totalmente opcional
    idade = models.IntegerField(null=True, blank=True)
    telefone = models.CharField(max_length=50, null=True, blank=True)

    # auto_now_add=True → preenche automaticamente com a data/hora atual só na criação
    criado_em = models.DateTimeField(auto_now_add=True)

    # auto_now=True → atualiza automaticamente para a data/hora atual em todo save()
    atualizado_em = models.DateTimeField(auto_now=True)

    def set_senha(self, senha_raw: str) -> None:
        """
        Recebe a senha pura (ex: "minhasenha123") e salva o hash no campo senha_hash.
        Exemplo de uso:
            usuario = Usuario(nome="ana", email="ana@email.com")
            usuario.set_senha("minhasenha123")
            usuario.save()
        """
        self.senha_hash = make_password(senha_raw)

    def __str__(self) -> str:
        # Define como o objeto aparece no admin e no terminal
        return f"{self.nome} <{self.email}>"


class LoginSocial(models.Model):
    """
    Armazena os vínculos de login via redes sociais (Google, Apple, etc.).
    Um usuário pode ter vários logins sociais — ex: entrar com Google E com Apple.
    Por isso é ForeignKey, muitos para um.
    """

    class Meta:
        # nome exato da tabela no banco de dados
        db_table = "login_social"
        # esses nomes aparecem no painel admin do Django
        verbose_name = "Login Social"
        verbose_name_plural = "Logins Sociais"
        constraints = [
            # Impede que o mesmo provider registre o mesmo uid duas vezes.
            # Ex: não pode ter dois registros com provider="google" e provider_uid="123".
            # Isso evita duplicidade se o usuário tentar conectar a mesma conta social duas vezes.
            models.UniqueConstraint(
                fields=["provider", "provider_uid"],
                name="uq_login_social_provider_uid",
            )
        ]

    # TextChoices cria um enum no Python com os valores aceitos pelo campo.
    # Cada linha tem: NOME_VARIAVEL_PYTHON = "valor_no_banco", "Label legível"
    class Provider(models.TextChoices):
        GOOGLE   = "google",   "Google"
        APPLE    = "apple",    "Apple"
        FACEBOOK = "facebook", "Facebook"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # ForeignKey = chave estrangeira → muitos LoginSocial podem pertencer a um Usuario
    # on_delete=CASCADE → se o Usuario for deletado, seus logins sociais também são deletados
    # related_name → permite acessar os logins de um usuário com: usuario.logins_sociais.all()
    # db_column → garante que o nome da coluna no banco seja "usuario_id"
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="logins_sociais",
        db_column="usuario_id",
    )

    # choices=Provider.choices → o Django só aceita os valores definidos no TextChoices acima
    # help_text → aparece como dica no admin e em formulários
    provider = models.CharField(
        max_length=50,
        choices=Provider.choices,
        help_text="Provedor OAuth (google, apple, facebook...)",
    )

    # O provider_uid é o ID que o Google/Apple/etc retorna após o login.
    # Ex: Google retorna algo como "117364823456789012345"
    # Usamos ele para identificar o usuário nas próximas vezes que ele logar
    provider_uid = models.CharField(
        max_length=255,
        help_text="ID único retornado pelo provedor OAuth",
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.provider} → {self.usuario.email}"


class Administrador(models.Model):
    """
    Perfil de administrador do sistema.
    Nem todo Usuario é administrador — apenas os que tiverem um registro aqui.
    """

    class Meta:
        # nome exato da tabela no banco de dados
        db_table = "administrador"
        # esses nomes aparecem no painel admin do Django
        verbose_name = "Administrador"
        verbose_name_plural = "Administradores"

    # Níveis de acesso disponíveis para administradores
    class NivelAcesso(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"  # acesso total
        MODERADOR   = "moderador",   "Moderador"    # acesso parcial

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=uuid.uuid4,
        editable=False,
    )

    # OneToOneField → um Usuario só pode ser administrador uma vez (relação 1 para 1)
    # É como um ForeignKey com unique=True, garante que não existam dois registros
    # de Administrador apontando para o mesmo Usuario
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="administrador",  # permite acessar com: usuario.administrador
        db_column="usuario_id",
    )

    # null=True + blank=True → nível de acesso é opcional.
    # Um administrador pode existir sem nível definido ainda.
    nivel_acesso = models.CharField(
        max_length=50,
        choices=NivelAcesso.choices,
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return f"{self.usuario.nome} [{self.nivel_acesso}]"