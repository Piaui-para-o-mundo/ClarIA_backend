

from typing import Literal

from pydantic import BaseModel, Field, EmailStr


class UserCreate(BaseModel):
    """ Schema para criacao de usuario (registro)."""

    nome: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    senha: str = Field(..., min_length=8, max_length=255)
    role: Literal["professor", "avaliador"]
    setor: str | None = Field(default=None, max_length=100)


class UserResponse(BaseModel):
    """Schema para response de usuário (seguro, sem senha)."""
    
    id: str
    nome: str
    email: str
    role: str
    setor: str | None
    ativo: bool
    
    model_config = {"from_attributes": True}

class TokenPayload(BaseModel):
    """Payload dentro do JWT."""
    
    sub: str  # User ID


class TokenResponse(BaseModel):
    """Response de login com JWT."""
    
    access_token: str
    token_type: str = "bearer"