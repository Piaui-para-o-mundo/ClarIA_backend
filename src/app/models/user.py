"""Modelo de usuário do banco de dados.

Define a tabela de usuários com campos para autenticação,
controle de roles e ativação de conta.
"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum
from app.core.connection import Base


class UserRole(str, Enum):
    """Roles disponíveis no sistema."""

    admin = "admin"
    professor = "professor"


class User(Base):
    """Modelo de usuário com autenticação via JWT."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, native_enum=False),
        default=UserRole.professor,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        """Representação em string do usuário."""
        return f"<User(id={self.id}, name={self.name}, email={self.email}, role={self.role})>"
