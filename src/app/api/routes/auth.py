
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi import Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

bearer_scheme = HTTPBearer()

@router.post("/register", response_model=UserResponse)
async def register(
    request: Request,
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
    # Accept JSON body or form-encoded data (from HTML forms)
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    user_data = UserCreate(**body)

    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado",
        )

    new_user = User(
        nome=user_data.nome,
        email=user_data.email,
        senha_hash=hash_password(user_data.senha),
        role=user_data.role,
        setor=user_data.setor,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user



@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Autentica usuário e retorna token JWT.
    
    Args:
        credentials: Dados de login (email, senha).
        db: Sessão de banco.
        
    Returns:
        TokenResponse: Token de acesso JWT.
        
    Raises:
        HTTPException: Se credenciais inválidas.
    """
    # Accept JSON or form data
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    credentials = UserLogin(**body)

    stmt = select(User).where(User.email == credentials.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not verify_password(credentials.senha, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.ativo:
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
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
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
    
    user = await get_current_user(token.credentials, db)
    return user