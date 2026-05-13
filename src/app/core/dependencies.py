"""Dependências de autenticação e autorização do FastAPI.

Módulo com dependências reutilizáveis para controlar acesso
baseado em tokens JWT e roles de usuário.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.connection import get_database_session
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.schemas.auth import TokenData

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_database_session),
) -> User:
    """
    Dependência para extrair e validar o usuário do token JWT.

    Args:
        credentials: Credenciais HTTP Bearer com o token JWT.
        db: Sessão do banco de dados.

    Returns:
        User: Usuário autenticado do banco de dados.

    Raises:
        HTTPException: Se o token for inválido, expirado ou usuário inativo.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependência que permite acesso apenas para usuários com role 'admin'.

    Args:
        current_user: Usuário autenticado.

    Returns:
        User: O usuário se tiver role de admin.

    Raises:
        HTTPException: Se o usuário não for admin.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current_user


def require_professor_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependência que permite acesso para 'professor' e 'admin'.

    Args:
        current_user: Usuário autenticado.

    Returns:
        User: O usuário se tiver role de professor ou admin.

    Raises:
        HTTPException: Se o usuário não tiver as roles necessárias.
    """
    if current_user.role not in {UserRole.admin, UserRole.professor}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a professores e administradores",
        )
    return current_user
