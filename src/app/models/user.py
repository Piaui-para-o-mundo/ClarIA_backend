
"""
Modelo Usuario — Professores e Avaliadores.

Campos:
- id: UUID, chave primária
- nome, email: Strings, unique email
- senha_hash: Armazenada com bcrypt
- role: Enum professor | avaliador
- setor: Opcional, ex: "Reitoria", "PROEN"
- ativo: Flag para soft-delete
- timestamps: criado_em, atualizado_em
"""

from datetime import datetime
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class para todos os modelos."""
    pass



class Role(str, PyEnum):
    """Roles disponiveis"""
    PROFESSOR = "professor"
    AVALIADOR = "avaliador"


RoleEnum = Role

class User(Base):
    """Modelo Usuario — Professores e Avaliadores."""
    __tablename__ = "usuarios"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        unique=True,
        index=True,
    )
    senha_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role),
        nullable=False,
        default=Role.PROFESSOR,
    )
    setor: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<Usuario {self.email} ({self.role})>"