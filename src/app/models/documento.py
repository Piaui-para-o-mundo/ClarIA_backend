

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class Documento(Base):
    """
    Documento associado a um processo.

    Armazena informacoes metadados e conteudo de PDFs/arquivos.
    """

    __tablename__ = "documentos"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    processo_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nome_arquivo: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    tipo_doc: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    caminho_arquivo: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    conteudo_extraido: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<Documento {self.nome_arquivo} ({self.tipo_doc})>"


        