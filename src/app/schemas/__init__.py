"""Pacote `schemas` - Pydantic schemas.
"""


from app.schemas.auth import (
    TokenPayload,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.schemas.documento import DocumentoResponse
from app.schemas.processo import (
    ProcessoCreate,
    ProcessoResponse,
    ProcessoResumo,
)


__all__ = [
    # Auth
    'UserCreate',
    'UserResponse',
    'TokenResponse',
    'TokenPayload',
    # Processo
    'ProcessoCreate',
    'ProcessoResponse',
    'ProcessoResumo',
    # Documento
    'DocumentoResponse',
]
