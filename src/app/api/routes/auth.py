"""Router de autenticação com endpoints de login e registro.

Expõe endpoints HTTP para autenticação de usuários
e gerenciamento de sessões.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.connection import get_database_session
from app.core.dependencies import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead, UserCreate
from app.services.auth_service import AuthService
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_database_session),
) -> TokenResponse:
    """
    Realiza login de um usuário.

    Args:
        login_data: Email e senha do usuário.
        db: Sessão do banco de dados.

    Returns:
        TokenResponse: Token JWT e dados do usuário.


    """
    auth_service = AuthService(db)
    return auth_service.login(login_data)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_database_session),
) -> UserRead:
    """
    Registra um novo usuário no sistema.

    Args:
        user_data: Dados do novo usuário.
        db: Sessão do banco de dados.

    Returns:
        UserRead: Dados do usuário criado.

    """
    auth_service = AuthService(db)
    user = auth_service.create_user(user_data)
    return UserRead.from_orm(user)


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """
    Retorna informações do usuário logado.

    Args:
        current_user: Usuário autenticado (injetado automaticamente).

    Returns:
        UserRead: Dados completos do usuário.

    """
    return UserRead.from_orm(current_user)
