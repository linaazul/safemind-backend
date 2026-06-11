from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Usuario, LoginSocial, Administrador


# USUARIO
class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer de LEITURA do usuário.
    Usado para retornar dados do usuário em respostas GET.
    Nunca expõe senha_hash.
    """
    class Meta:
        model = Usuario
        fields = [
            'id',
            'nome',
            'email',
            'idade',
            'telefone',
            'criado_em',
            'atualizado_em',
        ]
        # campos somente-leitura: o cliente não pode enviar esses valores
        read_only_fields = ['id', 'criado_em', 'atualizado_em']


class UsuarioCreateSerializer(serializers.ModelSerializer):
    """
    Serializer de CRIAÇÃO do usuário (cadastro).
    Separado do UsuarioSerializer porque aqui precisamos receber a senha
    em texto puro, fazer o hash, e nunca devolver o hash na resposta.

    Fluxo:
        1. Cliente envia nome, email, senha, senha_confirmacao,...
        2. Validamos que as senhas batem
        3. Transformamos a senha em hash antes de salvar
        4. Retornamos os dados sem a senha
    """

    # write_only=True → aceita o campo na entrada mas nunca devolve na resposta
    senha = serializers.CharField(write_only=True, min_length=8)
    senha_confirmacao = serializers.CharField(write_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id',
            'nome',
            'email',
            'senha',
            'senha_confirmacao',
            'idade',
            'telefone',
            'criado_em',
        ]
        read_only_fields = ['id', 'criado_em']

    def validate(self, data):
        """
        validate() roda depois de cada campo ser validado individualmente.
        Aqui comparamos os dois campos de senha.
        """
        if data['senha'] != data['senha_confirmacao']:
            raise serializers.ValidationError(
                {'senha_confirmacao': 'As senhas não coincidem.'}
            )
        return data

    def validate_email(self, value):
        """
        validate_<campo>() valida um campo específico.
        Aqui garantimos que o e-mail ainda não está cadastrado.
        """
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError('Este e-mail já está cadastrado.')
        return value.lower()  # normaliza para minúsculas antes de salvar

    def create(self, validated_data):
        """
        create() é chamado quando fazemos serializer.save() na view.
        Removemos senha_confirmacao (não existe no model) e
        transformamos a senha em hash antes de salvar.
        """
        validated_data.pop('senha_confirmacao')
        validated_data['senha_hash'] = make_password(validated_data.pop('senha'))
        return super().create(validated_data)


# JWT CUSTOMIZADO
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customiza o token JWT para incluir dados extras no payload.

    Por padrão o simplejwt só coloca o user_id no token.
    Aqui adicionamos nome, email e tipo de usuário para que o front
    não precise fazer uma segunda requisição só para saber quem está logado.

    O que cada token faz:
        - access token: token de curta duração (ex: 15 min) enviado em cada requisição
        - refresh token: token de longa duração (ex: 7 dias) usado só para gerar um novo access
    """

    @classmethod
    def get_token(cls, user):
        # chama o método pai que gera o token base
        token = super().get_token(user)

        # adicionamos campos extras no PAYLOAD do token
        # atenção: não coloque dados sensíveis aqui (o payload é apenas encoded, não criptografado)
        token['nome'] = user.nome
        token['email'] = user.email

        # identifica o tipo do usuário para o front saber qual dashboard exibir
        if hasattr(user, 'administrador'):
            token['tipo'] = 'administrador'
        elif hasattr(user, 'terapeuta'):
            token['tipo'] = 'terapeuta'
        elif hasattr(user, 'paciente'):
            token['tipo'] = 'paciente'
        else:
            token['tipo'] = 'usuario'

        return token

    def validate(self, attrs):
        """
        Além do token, adicionamos dados extras na RESPOSTA do login.
        Isso é diferente do payload acima: aqui é o JSON que o cliente recebe,
        não o que fica dentro do token.
        """
        data = super().validate(attrs)

        # inclui dados do usuário direto na resposta do login
        # assim o front já tem o que precisa sem chamada extra
        data['usuario'] = {
            'id': self.user.id,
            'nome': self.user.nome,
            'email': self.user.email,
        }
        return data


# LOGIN SOCIAL
class LoginSocialSerializer(serializers.ModelSerializer):
    """
    Registra um login via provedor social (Google, Facebook).

    Fluxo de login social:
        1. Front autentica com Google/Facebook e recebe um provider_uid
        2. Envia { provider, provider_uid } para nossa API
        3. Se já existir, retorna o usuário vinculado
        4. Se não existir, cria o registro e vincula ao usuário
    """

    class Meta:
        model = LoginSocial
        fields = [
            'id',
            'usuario_id',
            'provider',      # ex: 'google', 'facebook'
            'provider_uid',  # ID único retornado pelo provedor
            'criado_em',
        ]
        read_only_fields = ['id', 'criado_em']

    def validate_provider(self, value):
        """Garante que só aceitamos provedores conhecidos."""
        provedores_aceitos = ['google', 'facebook', 'apple']
        if value.lower() not in provedores_aceitos:
            raise serializers.ValidationError(
                f'Provedor inválido. Aceitos: {", ".join(provedores_aceitos)}'
            )
        return value.lower()

    def validate(self, data):
        """Garante que não existe duplicata para o mesmo provedor + uid."""
        if LoginSocial.objects.filter(
            provider=data['provider'],
            provider_uid=data['provider_uid']
        ).exists():
            raise serializers.ValidationError(
                'Este login social já está vinculado a uma conta.'
            )
        return data


# ADMINISTRADOR
class AdministradorSerializer(serializers.ModelSerializer):
    """
    Serializer do Administrador.
    Inclui dados do usuário vinculado como campo aninhado (read-only).
    """

    # SerializerMethodField permite criar um campo calculado/customizado
    # aqui buscamos os dados do usuário relacionado para incluir na resposta
    usuario = serializers.SerializerMethodField()

    class Meta:
        model = Administrador
        fields = [
            'id',
            'usuario_id',
            'usuario',        # campo aninhado com dados do usuário
            'nivel_acesso',
        ]
        read_only_fields = ['id']

    def get_usuario(self, obj):
        """
        get_<campo>() é chamado automaticamente para campos SerializerMethodField.
        obj = instância do Administrador sendo serializado.
        """
        return {
            'nome': obj.usuario_id.nome,
            'email': obj.usuario_id.email,
        }