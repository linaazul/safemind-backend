# IMPORTS
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Usuario, LoginSocial, Administrador
from .serializers import (
    UsuarioSerializer,
    UsuarioCreateSerializer,
    LoginSocialSerializer,
    AdministradorSerializer,
    CustomTokenObtainPairSerializer,
)


# USUARIO
class UsuarioViewSet(viewsets.ModelViewSet):
    """
    ViewSet do Usuário.

    O ModelViewSet já nos dá 5 actions prontas automaticamente:
        list()      → GET  /usuarios/         → lista todos
        create()    → POST /usuarios/         → cria novo
        retrieve()  → GET  /usuarios/{id}/    → busca um
        update()    → PUT  /usuarios/{id}/    → edita tudo
        partial_update() → PATCH /usuarios/{id}/ → edita parte
        destroy()   → DELETE /usuarios/{id}/ → deleta

    Além dessas, criamos actions customizadas com @action.
    """

    queryset = Usuario.objects.all()

    # get_serializer_class() decide qual serializer usar dependendo da action.
    # Isso resolve o problema de ter dois serializers para o mesmo model:
    # um para criação (com senha) e outro para leitura (sem senha).
    def get_serializer_class(self):
        if self.action == 'create':
            return UsuarioCreateSerializer  # recebe senha, faz hash
        return UsuarioSerializer            # leitura segura, sem senha

    # get_permissions() decide quais permissões aplicar por action.
    def get_permissions(self):
        if self.action == 'create':
            # qualquer um pode se cadastrar, nem precisa estar logado
            return [AllowAny()]
        if self.action in ['list', 'destroy']:
            # só admin pode listar todos os usuários ou deletar
            return [IsAdminUser()]
        # para retrieve, update, partial_update e actions customizadas:
        # precisa estar autenticado
        return [IsAuthenticated()]

    # ACTIONS CUSTOMIZADAS
    # @action cria endpoints extras além dos 5 padrão do ViewSet.
    # Parâmetros:
    #   detail=True  → /usuarios/{id}/minha_action/  (age sobre um registro específico)
    #   detail=False → /usuarios/minha_action/        (age sobre a coleção)
    #   methods      → quais métodos HTTP aceita
    #   url_path     → o nome que aparece na URL (padrão é o nome da função)
    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def me(self, request):
        """
        GET/PUT/PATCH /usuarios/me/

        Retorna ou atualiza o perfil do usuário logado.
        O front não precisa saber o ID do usuário, o token já identifica quem é.
        request.user é populado automaticamente pelo JWT quando o token é válido.
        """
        usuario = request.user  # usuário extraído do token JWT

        if request.method == 'GET':
            serializer = UsuarioSerializer(usuario)
            return Response(serializer.data)

        # PUT ou PATCH: atualiza os dados
        # partial=True permite enviar só os campos que quer alterar (PATCH)
        partial = request.method == 'PATCH'
        serializer = UsuarioSerializer(usuario, data=request.data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        # is_valid() retorna False se alguma validação falhou.
        # serializer.errors contém os detalhes de cada campo com problema.
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='deletar-conta',
            permission_classes=[IsAuthenticated])
    def deletar_conta(self, request):
        """
        POST /usuarios/deletar-conta/

        Permite que o próprio usuário delete sua conta (RF15).
        Usamos POST ao invés de DELETE porque o front pode querer
        enviar um motivo ou confirmação no body da requisição.
        """
        usuario = request.user
        usuario.delete()
        return Response(
            {'mensagem': 'Conta deletada com sucesso.'},
            status=status.HTTP_204_NO_CONTENT
        )

# JWT / LOGIN
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /contas/token/

    Substitui a view padrão do simplejwt pelo nosso serializer customizado,
    que injeta nome, email e tipo do usuário no token e na resposta.

    O cliente envia:
        { "email": "...", "password": "..." }    ← o simplejwt usa "password" por padrão

    E recebe:
        {
            "access": "eyJ...",      ← token de curta duração, enviado em cada requisição
            "refresh": "eyJ...",     ← token de longa duração, usado só para renovar o access
            "usuario": { "id", "nome", "email" }
        }
    """
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """
    POST /contas/logout/

    No JWT, o logout é feito invalidando o refresh token.
    O access token continua válido até expirar (por isso ele tem curta duração),
    mas sem o refresh token o cliente não consegue renovar o acesso.

    O cliente envia:
        { "refresh": "eyJ..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'erro': 'Token de refresh não fornecido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # blacklist() marca o token como inválido no banco de dados.
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {'mensagem': 'Logout realizado com sucesso.'},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {'erro': 'Token inválido ou já expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )


# LOGIN SOCIAL
class LoginSocialViewSet(viewsets.ModelViewSet):
    """
    ViewSet para logins via Google e Facebook.

    Fluxo completo:
        1. Front autentica com Google/Facebook usando o SDK deles
        2. Recebe um provider_uid (ID único do usuário naquele provedor)
        3. Envia para nossa API: { usuario_id, provider, provider_uid }
        4. Nossa API registra o vínculo
    """
    queryset = LoginSocial.objects.all()
    serializer_class = LoginSocialSerializer

    def get_permissions(self):
        if self.action == 'create':
            # o login social é chamado durante o processo de autenticação,
            # então não exigimos token ainda
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Sobrescrevemos o queryset para que cada usuário só veja
        seus próprios logins sociais, nunca os de outros.
        Admins veem todos.
        """
        user = self.request.user
        if user.is_staff:
            return LoginSocial.objects.all()
        return LoginSocial.objects.filter(usuario_id=user.id)

# ADMINISTRADOR
class AdministradorViewSet(viewsets.ModelViewSet):
    """
    ViewSet do Administrador.
    Todos os endpoints exigem permissão de admin (IsAdminUser).
    Apenas admins podem gerenciar outros admins.
    """
    queryset = Administrador.objects.all()
    serializer_class = AdministradorSerializer
    permission_classes = [IsAdminUser]