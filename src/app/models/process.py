

from datetime import datetime
from enum import Enum as pyEnum
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base

class StatusEnum(str, pyEnum):
    AGUARDANDO_DOCUMENTOS = "aguardando_documentos"
    AGUARDANDO_ANALISE = "aguardando_analise"
    EM_ANALISE = "em_analise"
    ANALISE_PENDENTE = "analise_pendente"
    PENDENTE_PROFESSOR = "pendente_professor"
    CONCLUIDO = "concluido"
    APROVADO = "aprovado"
    REPROVADO = "reprovado"


class AnaliseStatusEnum(str, pyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class Process(Base):
    """
    Processo de requerimento.

    Representa um requerimento de professor(progressao, promocao, etc. )
    com seus documentos e analises
    """

    __tablename__ = "processos"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    numero: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[StatusEnum] = mapped_column(
        Enum(StatusEnum),
        nullable=False,
        default=StatusEnum.AGUARDANDO_ANALISE,
        index=True,
    )
    resumo_ia: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Resumo executivo gerado pelo serviço RAG",
    )
    checklist_ia: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Resultado do checklist determinístico (JSON)",
    )
    despacho_automatico: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    despacho_avaliador: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    documentos: Mapped[list["Documento"]] = relationship(
        "Documento",
        backref="processo",
        lazy="selectin",
    )
    
    usuario = relationship(
        "User",
        lazy="joined"
    )
    
    @property
    def setor_remetente(self) -> str | None:
        if getattr(self, "usuario", None):
            return self.usuario.setor
        return None
    
    def __repr__(self) -> str:
        return f"<Processo {self.numero} - {self.status}>"


Processo = Process