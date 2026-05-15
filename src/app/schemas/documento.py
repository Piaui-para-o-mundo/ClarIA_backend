

from datetime import datetime

from pydantic import BaseModel


class DocumentoResponse(BaseModel):
    """Schema para response de documento."""
    
    id: str
    processo_id: str
    nome_arquivo: str
    tipo_doc: str
    caminho_arquivo: str
    conteudo_extraido: str | None
    criado_em: datetime
    
    model_config = {"from_attributes": True}