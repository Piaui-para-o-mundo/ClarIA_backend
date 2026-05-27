"""Schemas Pydantic para Notificações."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificacaoResponse(BaseModel):
    """Schema de resposta para uma notificação."""

    id: UUID
    usuario_id: UUID
    processo_id: UUID | None = None
    tipo: str
    titulo: str
    mensagem: str
    lida: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


class NotificacaoResumo(BaseModel):
    """Schema resumido para contagem e listagem rápida."""

    total_nao_lidas: int
    notificacoes: list[NotificacaoResponse]
