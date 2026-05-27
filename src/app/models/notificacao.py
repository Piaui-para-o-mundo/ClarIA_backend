"""
Modelo Notificação — Notificações in-app para professores e avaliadores.

Campos:
- id: UUID, chave primária
- usuario_id: FK para o usuário destinatário
- processo_id: FK opcional para o processo relacionado
- tipo: Tipo de notificação (despacho_automatico, pendencia, etc.)
- titulo: Título curto da notificação
- mensagem: Corpo da notificação
- lida: Flag booleana
- timestamps: criado_em
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class Notificacao(Base):
    """Notificação in-app para usuários do sistema."""

    __tablename__ = "notificacoes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    processo_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="info",
        comment="Tipo: despacho_automatico, pendencia, info",
    )
    titulo: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    mensagem: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    lida: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    usuario = relationship("User", lazy="joined")
    processo = relationship("Process", lazy="joined")

    def __repr__(self) -> str:
        return f"<Notificacao {self.titulo} -> {self.usuario_id} ({'lida' if self.lida else 'não lida'})>"
