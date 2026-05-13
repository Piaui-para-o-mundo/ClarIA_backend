"""Schemas de autenticação para login e tokens.

Define os contracts Pydantic para operações de autenticação.
"""

from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """Schema para requisição de login."""

    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha do usuário")


class TokenResponse(BaseModel):
    """Schema para resposta de autenticação com token."""

    access_token: str = Field(..., description="JWT token de acesso")
    token_type: str = Field(default="bearer", description="Tipo do token")
    user: UserRead = Field(..., description="Dados do usuário autenticado")


class TokenData(BaseModel):
    """Schema para dados decodificados do token JWT."""

    user_id: int | None = None
    email: str | None = None
    role: str | None = None
