

from typing import Annotated

from fastapi import Depends, HTTPException, status
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import TokenPayload
from sqlalchemy.ext.asyncio import AsyncSession

async def get_current_user(
    token: str,
    db: AsyncSession
) -> User:
    """
    Dependency que valida JWT e retorna usuario logado.

    Args:
        token: JWT extraido do header Authorization.
        db: Sessao do banco.

    Returns: 
        Usuario: Usuario logado.

    Raises:
        HTTPException: Se token for invalido ou usuario nao existir.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nao foi possivel validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id)
    except JWTError:
        raise credentials_exception
    

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception
    
    return user

def get_current_active_user(*allowed_roles: str):
    """
    Factory de dependency que valida role do usuario

    Args:
        allowed_roles: Roles permitidas (ex: "professor", "avaliador").

    Returns:
        Callable: Dependency que poder ser usado em rotas.
    
    raises:
        HTTPException: Se usuario nao tem role permitido.
    """

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: Roles permitidas: {', '.join(allowed_roles)}",
            )
        return current_user
    return role_checker


require_role = get_current_active_user
    