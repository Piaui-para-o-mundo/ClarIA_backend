
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Registra novo usuário.
    
    Args:
        user_data: Dados do usuário (nome, email, senha, role).
        db: Sessão de banco.
        
    Returns:
        UserResponse: Usuário criado (sem senha).
        
    Raises:
        HTTPException: Se email já existe.
    """
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado",
        )

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        setor=user_data.setor,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user



@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    """
    Autentica usuário e retorna token JWT.
    
    Args:
        form_data: Dados de login (email, senha).
        db: Sessão de banco.
        
    Returns:
        TokenResponse: Token de acesso JWT.
        
    Raises:
        HTTPException: Se credenciais inválidas.
    """
    stmt = select(User).where(User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )
    
    access_token_expires = timedelta(hours=1)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
): 
    """
    Retorna dados do usuário logado.
    
    Args:
        token: JWT do header Authorization.
        db: Sessão de banco.
        
    Returns:
        UserResponse: Dados do usuário.
    """
    from app.core.dependencies import get_current_user
    
    user = await get_current_user(token, db)
    return user