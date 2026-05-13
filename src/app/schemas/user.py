"""Schemas de usuário para validação de entrada e saída.

Define os contracts Pydantic para operações com usuários.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole


class UserCreate(BaseModel):
    """Schema para criar um novo usuário."""

    name: str = Field(..., min_length=1, max_length=255, description="Nome do usuário")
    email: EmailStr = Field(..., description="Email único do usuário")
    password: str = Field(..., min_length=6, description="Senha (mínimo 6 caracteres)")
    role: UserRole = Field(default=UserRole.professor, description="Role do usuário")


class UserRead(BaseModel):
    """Schema para retornar dados do usuário."""

    id: int
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema para atualizar um usuário."""

    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None
