from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.documento import DocumentoResponse


class ProcessoCreate(BaseModel):
    """Schema para criação de processo."""

    tipo: Literal[
        'afastamento_pos_graduacao',
        'afastamento_pos_doutorado',
        'alteracao_regime_dedicacao_exclusiva',
        'alteracao_regime_tp20h_para_ti40h',
        'alteracao_regime_reducao',
        'estagio_probatorio',
        'licenca_capacitacao',
        'licenca_premio',
        'progressao_funcional',
        'promocao_titulo',
        'promocao_associado',
        'promocao_titular',
    ]


class ProcessoResumo(BaseModel):
    """Schema resumido de processo (para listagem)."""

    id: UUID
    numero: str
    tipo: str
    status: str
    setor_remetente: str | None = None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {'from_attributes': True}


class ProcessoResponse(BaseModel):
    """Schema completo de processo com documentos e resultado da IA."""

    id: UUID
    numero: str
    tipo: str
    status: str
    analise_status: str | None = None
    analise_erro: str | None = None
    usuario_id: UUID
    setor_remetente: str | None = None
    # Resultado da análise automática pelo RAG (preenchido pelo BackgroundTask)
    resumo_ia: str | None = None
    checklist_ia: str | None = None
    despacho_automatico: str | None = None
    # Despacho editado e aprovado pelo avaliador
    despacho_avaliador: str | None = None
    criado_em: datetime
    atualizado_em: datetime
    documentos: list[DocumentoResponse] = Field(default_factory=list)

    model_config = {'from_attributes': True}


class AnaliseStatusResponse(BaseModel):
    """Schema para o status da análise automática do processo."""

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

    model_config = {'from_attributes': True}
