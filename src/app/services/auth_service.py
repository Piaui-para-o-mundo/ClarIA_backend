"""Serviço de autenticação e login.

Centraliza a lógica de validação de credenciais,
geração de tokens e manipulação de usuários.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead, UserCreate
from app.core.security import hash_password, verify_password, create_access_token


class AuthService:
    """Serviço de autenticação e gerenciamento de usuários."""

    def __init__(self, db: Session):
        """
        Inicializa o serviço com a sessão do banco de dados.

        Args:
            db: Sessão SQLAlchemy do banco de dados.
        """
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        """
        Busca um usuário pelo email.

        Args:
            email: Email do usuário.

        Returns:
            User: Usuário encontrado ou None.
        """
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user_data: UserCreate) -> User:
        """
        Cria um novo usuário no banco de dados.

        Args:
            user_data: Dados do usuário a criar.

        Returns:
            User: Usuário criado.

        Raises:
            HTTPException: Se o email já está em uso.
        """
        existing_user = self.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já registrado",
            )

        hashed_password = hash_password(user_data.password)
        db_user = User(
            name=user_data.name,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role,
            is_active=True,
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return db_user

    def authenticate_user(self, email: str, password: str) -> User | None:
        """
        Autentica um usuário verificando email e senha.

        Args:
            email: Email do usuário.
            password: Senha em texto plano.

        Returns:
            User: Usuário autenticado ou None se falhar.
        """
        user = self.get_user_by_email(email)

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        return user

    def login(self, login_data: LoginRequest) -> TokenResponse:
        """
        Realiza login e retorna token JWT com dados do usuário.

        Args:
            login_data: Credenciais de login (email e senha).

        Returns:
            TokenResponse: Token de acesso e dados do usuário.

        Raises:
            HTTPException: Se as credenciais forem inválidas.
        """
        user = self.authenticate_user(login_data.email, login_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha inválidos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Criar token com dados do usuário
        token_data = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value,
        }
        access_token = create_access_token(data=token_data)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserRead.from_orm(user),
        )
