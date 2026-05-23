
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.documento import DocumentoResponse


class ProcessoCreate(BaseModel):
    """Schema para criação de processo."""
    tipo: Literal[
        "progressao_funcional",
        "promocao",
        "afastamento_mestrado",
        "licenca_premio",
        "outros"
    ]


class ProcessoResumo(BaseModel):
    """Schema resumido de processo (para listagem)."""

    id: UUID
    numero: str
    tipo: str
    status: str
<<<<<<< HEAD
    analise_status: str
=======
    setor_remetente: str | None = None
>>>>>>> 4cb46e6 (fix(processo): clean up formatting and improve docstring for ProcessoResponse schema)
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class ProcessoResponse(BaseModel):
    """Schema completo de processo com documentos e resultado da IA."""

    id: UUID
    numero: str
    tipo: str
    status: str
    analise_status: str
    usuario_id: UUID
    analise_started_em: datetime | None = None
    analise_concluida_em: datetime | None = None
    analise_erro: str | None = None
    analise_log: str | None = None
    resumo_ia: str | None = None
    checklist_ia: str | None = None
    despacho_automatico: str | None
    despacho_avaliador: str | None
    criado_em: datetime
    atualizado_em: datetime
    documentos: list[DocumentoResponse] = Field(default_factory=list)
    
    model_config = {"from_attributes": True}


class AnaliseStatusResponse(BaseModel):
    """Schema para acompanhar o estado da análise automática."""

    processo_id: UUID
    analise_status: str
    status: str
    analise_started_em: datetime | None = None
    analise_concluida_em: datetime | None = None
    analise_erro: str | None = None
    analise_log: str | None = None
    resumo_ia: str | None = None
    checklist_ia: str | None = None
    despacho_automatico: str | None = None

    model_config = {"from_attributes": True}