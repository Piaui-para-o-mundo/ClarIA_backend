
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from  app.schemas.documento import DocumentoResponse

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
    
    id: str
    numero: str
    tipo: str
    status: str
    criado_em: datetime
    atualizado_em: datetime
    
    model_config = {"from_attributes": True}


class ProcessoResponse(BaseModel):
    """Schema completo de processo com documentos."""
    
    id: str
    numero: str
    tipo: str
    status: str
    usuario_id: str
    despacho_automatico: str | None
    despacho_avaliador: str | None
    criado_em: datetime
    atualizado_em: datetime
    documentos: list[DocumentoResponse] = Field(default_factory=list)
    
    model_config = {"from_attributes": True}