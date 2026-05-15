# 📚 Guia Completo de Implementação — ClarIA Backend MVP

> **Status:** Documento consolidado de desenvolvimento  
> **Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy Async · Alembic  
> **Data:** 2026-05-12

---

## 🎯 Índice de Arquivos

Este documento lista **todos os arquivos** que precisam ser criados/modificados, na ordem de dependência, com código pronto para implementação.

---

# FASE 1 — FUNDAÇÃO

## 📄 `requirements.txt`

```txt
# Core
fastapi>=0.136.0
uvicorn[standard]>=0.31.0
python-multipart>=0.0.7

# Database
sqlalchemy[asyncio]>=2.0
asyncpg>=0.30.0
alembic>=1.13.0

# Security
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-dotenv>=1.0.0

# Validation & Settings
pydantic>=2.0
pydantic-settings>=2.1.0
pydantic[email]>=2.0

# HTTP Client
httpx>=0.27.0

# Utilities
python-dateutil>=2.8.2
```

---

## 📄 `.env.example`

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/claria_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=claria_db

# Security
SECRET_KEY=your-secret-key-change-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Services
RAG_SERVICE_URL=http://localhost:8001
RAG_SERVICE_TIMEOUT=120

# Environment
ENVIRONMENT=development
DEBUG=True
```

---

## 📄 `app/config.py`

```python
"""
Configurações centralizadas da aplicação.

Usa Pydantic Settings para validação e gerenciamento de variáveis de ambiente.
Padrão: Settings como singleton (instanciado uma vez no boot).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configurações da aplicação.
    
    Atributos validados via Pydantic com valores padrão e tipos seguros.
    """
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # Security
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Services
    rag_service_url: str = Field(default="http://localhost:8001", alias="RAG_SERVICE_URL")
    rag_service_timeout: int = Field(default=120, alias="RAG_SERVICE_TIMEOUT")
    
    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    
    class Config:
        """Configurações do Pydantic."""
        env_file = ".env"
        case_sensitive = False
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    """
    Retorna configurações (cached).
    
    Returns:
        Settings: Instância única de configurações.
    """
    return Settings()
```

---

## 📄 `app/core/database.py`

```python
"""
Configuração do banco de dados com SQLAlchemy Async.

Implementa:
- Engine assíncrono
- Session factory assíncrona
- Dependency injection para get_db()
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def get_engine() -> AsyncEngine:
    """
    Cria engine SQLAlchemy assíncrono.
    
    Returns:
        AsyncEngine: Engine conectado ao banco.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
        pool_size=10,
        max_overflow=20,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """
    Factory para criar sessions assíncronas.
    
    Args:
        engine: AsyncEngine configurado.
        
    Returns:
        async_sessionmaker: Factory para gerar sessions.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Instâncias globais
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


async def init_db() -> None:
    """
    Inicializa database na startup da aplicação.
    
    Cria engine e session factory. Pode ser expandido para criar tabelas.
    """
    global _engine, _session_factory
    _engine = get_engine()
    _session_factory = get_session_factory(_engine)


async def close_db() -> None:
    """
    Fecha conexões com database na shutdown da aplicação.
    """
    global _engine
    if _engine:
        await _engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection para obter session de banco.
    
    Yields:
        AsyncSession: Session assíncrona do banco.
    """
    global _session_factory
    if not _session_factory:
        raise RuntimeError("Database não foi inicializado. Chame init_db() na startup.")
    
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## 📄 `app/core/security.py`

```python
"""
Utilitários de segurança: hashing de senha e JWT.

Padrão: Funções puras sem estado, seguras para uso concorrente.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings


# Context para hash bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """
    Hash de senha usando bcrypt.
    
    Args:
        password: Senha em plaintext.
        
    Returns:
        str: Hash bcrypt da senha.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se senha em plaintext corresponde ao hash.
    
    Args:
        plain_password: Senha em plaintext.
        hashed_password: Hash bcrypt armazenado.
        
    Returns:
        bool: True se senhas correspondem, False caso contrário.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Cria JWT access token.
    
    Args:
        data: Payload a encodar (ex: {"sub": user_id}).
        expires_delta: Duração do token. Se None, usa settings.
        
    Returns:
        str: Token JWT encodado.
    """
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodifica JWT access token.
    
    Args:
        token: Token JWT.
        
    Returns:
        Dict: Payload decodificado.
        
    Raises:
        JWTError: Se token for inválido ou expirado.
    """
    settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Token inválido ou expirado: {str(e)}")
```

---

## 📄 `app/core/dependencies.py`

```python
"""
Dependências globais para injeção em rotas.

Implementa:
- get_db(): Retorna AsyncSession
- get_current_user(): Valida JWT e retorna usuário
- require_role(): Factory de validadores de role
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token
from app.models.usuario import Usuario
from app.schemas.auth import TokenPayload
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user(
    token: Annotated[str, Depends(lambda: "")],  # Será sobrescrito
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Dependency que valida JWT e retorna usuário logado.
    
    Args:
        token: JWT extraído do header Authorization.
        db: Sessão do banco.
        
    Returns:
        Usuario: Usuário logado.
        
    Raises:
        HTTPException: Se token inválido ou usuário não existe.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id)
    except JWTError:
        raise credentials_exception
    
    from sqlalchemy import select
    
    result = await db.execute(select(Usuario).where(Usuario.id == token_data.sub))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    
    return user


def require_role(*allowed_roles: str):
    """
    Factory de dependency que valida role do usuário.
    
    Args:
        *allowed_roles: Roles permitidos (ex: "professor", "avaliador").
        
    Returns:
        Callable: Dependency que pode ser usado em rotas.
        
    Raises:
        HTTPException: Se usuário não tem role permitido.
    """
    async def role_checker(
        current_user: Annotated[Usuario, Depends(get_current_user)]
    ) -> Usuario:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Roles permitidas: {', '.join(allowed_roles)}",
            )
        return current_user
    
    return role_checker
```

---

# FASE 2 — MODELOS DE DADOS

## 📄 `app/models/__init__.py`

```python
"""
Modelos SQLAlchemy (ORM).

Expõe all models para uso em migrations e queries.
"""

from app.models.documento import Documento
from app.models.processo import Processo
from app.models.usuario import Usuario

__all__ = ["Usuario", "Processo", "Documento"]
```

---

## 📄 `app/models/usuario.py`

```python
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


class RoleEnum(str, PyEnum):
    """Roles disponíveis."""
    PROFESSOR = "professor"
    AVALIADOR = "avaliador"


class Usuario(Base):
    """
    Usuário do sistema.
    
    Representação ORM de um usuário (professor ou avaliador).
    """
    
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
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum),
        nullable=False,
        default=RoleEnum.PROFESSOR,
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
```

---

## 📄 `app/models/processo.py`

```python
"""
Modelo Processo — Requerimentos de Professores.

Campos:
- id: UUID
- numero: String unique (ex: CPPD-001/2026)
- usuario_id: FK → Usuario
- tipo: String (progressao_funcional, promocao, etc.)
- status: Enum (aguardando_analise, pendente_professor, etc.)
- despacho_automatico: Texto gerado pelo RAG
- despacho_avaliador: Texto final após avaliador aprovar
- timestamps
"""

from datetime import datetime
from enum import Enum as PyEnum
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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.usuario import Base


class StatusEnum(str, PyEnum):
    """Status do processo."""
    AGUARDANDO_ANALISE = "aguardando_analise"
    PENDENTE_PROFESSOR = "pendente_professor"
    ANALISE_PENDENTE = "analise_pendente"
    CONCLUIDO = "concluido"
    ARQUIVADO = "arquivado"


class Processo(Base):
    """
    Processo de requerimento.
    
    Representa um requerimento de professor (progressão, promoção, etc.)
    com seus documentos e análises.
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
    
    def __repr__(self) -> str:
        return f"<Processo {self.numero} - {self.status}>"
```

---

## 📄 `app/models/documento.py`

```python
"""
Modelo Documento — Arquivos do Processo.

Campos:
- id: UUID
- processo_id: FK → Processo
- nome_arquivo: String
- tipo_doc: String (requerimento, cpf, contracheque, etc.)
- caminho_arquivo: String (path no disco)
- conteudo_extraido: Text opcional (texto extraído pelo RAG)
- timestamps
"""

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

from app.models.usuario import Base


class Documento(Base):
    """
    Documento associado a um processo.
    
    Armazena metadados e conteúdo de PDFs/arquivos.
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
```

---

# FASE 3 — SCHEMAS (Pydantic)

## 📄 `app/schemas/__init__.py`

```python
"""
Schemas Pydantic para validação de requests/responses.
"""

from app.schemas.auth import TokenPayload, TokenResponse, UserCreate, UserResponse
from app.schemas.documento import DocumentoResponse
from app.schemas.processo import ProcessoCreate, ProcessoResponse, ProcessoResumo

__all__ = [
    # Auth
    "UserCreate",
    "UserResponse",
    "TokenResponse",
    "TokenPayload",
    # Processo
    "ProcessoCreate",
    "ProcessoResponse",
    "ProcessoResumo",
    # Documento
    "DocumentoResponse",
]
```

---

## 📄 `app/schemas/auth.py`

```python
"""
Schemas de autenticação.

- UserCreate: Request de registro
- UserResponse: Response de usuário
- TokenResponse: Response de login (JWT)
- TokenPayload: Dados dentro do JWT
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema para criação de usuário (registro)."""
    
    nome: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    senha: str = Field(..., min_length=8, max_length=255)
    role: Literal["professor", "avaliador"]
    setor: str | None = Field(default=None, max_length=100)


class UserResponse(BaseModel):
    """Schema para response de usuário (seguro, sem senha)."""
    
    id: str
    nome: str
    email: str
    role: str
    setor: str | None
    ativo: bool
    
    model_config = {"from_attributes": True}


class TokenPayload(BaseModel):
    """Payload dentro do JWT."""
    
    sub: str  # User ID


class TokenResponse(BaseModel):
    """Response de login com JWT."""
    
    access_token: str
    token_type: str = "bearer"
```

---

## 📄 `app/schemas/processo.py`

```python
"""
Schemas de processo.

- ProcessoCreate: Request para criar processo
- ProcessoResponse: Response completo com documentos
- ProcessoResumo: Versão simplificada para listagem
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.documento import DocumentoResponse


class ProcessoCreate(BaseModel):
    """Schema para criação de processo."""
    
    tipo: Literal[
        "progressao_funcional",
        "promocao",
        "afastamento_mestrado",
        "afastamento_doutorado",
        "licenca_premio",
        "outro",
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
```

---

## 📄 `app/schemas/documento.py`

```python
"""
Schemas de documento.

- DocumentoResponse: Response de documento
"""

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
```

---

# FASE 4 — SERVICES

## 📄 `app/services/__init__.py`

```python
"""
Services (camada de lógica de negócio).

Separa regra de negócio das rotas.
"""

from app.services.processo_service import ProcessoService
from app.services.rag_client import RAGClient

__all__ = ["ProcessoService", "RAGClient"]
```

---

## 📄 `app/services/rag_client.py`

```python
"""
Client HTTP para chamar ClarIA_RAG_IA.

Implementa:
- health_check
- ingest_documento
- gerar_resumo
- verificar_conformidade
- sugerir_despacho

Padrão: Todas operações são assíncronas com httpx.
"""

from typing import Any

import httpx

from app.config import get_settings


class RAGClient:
    """
    Cliente assíncrono para o serviço RAG.
    
    Abstrai a comunicação HTTP com ClarIA_RAG_IA.
    Todos os métodos são corrotinas.
    """
    
    def __init__(self, base_url: str, timeout: int = 120):
        """
        Inicializa cliente.
        
        Args:
            base_url: URL base do serviço RAG (ex: http://localhost:8001).
            timeout: Timeout em segundos para requisições.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def health_check(self) -> bool:
        """
        Verifica saúde do serviço RAG.
        
        Returns:
            bool: True se RAG está healthy, False caso contrário.
        """
        try:
            response = await self.client.get(f"{self.base_url}/ia/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def ingest_documento(self, pdf_content: bytes, filename: str) -> dict[str, Any]:
        """
        Envia PDF para indexação no ChromaDB do RAG.       Args:
            pdf_content: Conteúdo binário do PDF.
            filename: Nome do arquivo.
            
        Returns:
            dict: Resposta do RAG com índice/ID do documento.
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        files = {
            "file": (filename, pdf_content, "application/pdf"),
        }
        response = await self.client.post(
            f"{self.base_url}/ia/ingest",
            files=files,
        )
        response.raise_for_status()
        return response.json()
    
    async def gerar_resumo(self, texto_documento: str) -> dict[str, Any]:
        """
        Módulo 1 do RAG: Gera resumo inteligente de texto.
        
        Args:
            texto_documento: Texto do documento.
            
        Returns:
            dict: {"resumo": str, "palavras_chave": list[str], ...}
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        payload = {"texto": texto_documento}
        response = await self.client.post(
            f"{self.base_url}/ia/resumo",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def verificar_conformidade(
        self,
        texto_documento: str,
        tipo_processo: str,
    ) -> dict[str, Any]:
        """
        Módulo 2 do RAG: Verifica conformidade documental.
        
        Args:
            texto_documento: Texto do documento.
            tipo_processo: Tipo de processo (progressao_funcional, etc.).
            
        Returns:
            dict: {
                "conformidade_pct": float,
                "pendencias": list[str],
                "detalhes": dict,
            }
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        payload = {
            "texto": texto_documento,
            "tipo_processo": tipo_processo,
        }
        response = await self.client.post(
            f"{self.base_url}/ia/conformidade",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def sugerir_despacho(
        self,
        texto_documento: str,
        pendencias: str,
    ) -> dict[str, Any]:
        """
        Módulo 3 do RAG: Sugere despacho para o avaliador.
        
        Args:
            texto_documento: Texto do documento.
            pendencias: Descrição das pendências.
            
        Returns:
            dict: {"despacho": str, "motivo": str, ...}
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        payload = {
            "texto": texto_documento,
            "pendencias": pendencias,
        }
        response = await self.client.post(
            f"{self.base_url}/ia/despacho",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self) -> None:
        """Fecha cliente HTTP."""
        await self.client.aclose()


async def get_rag_client() -> RAGClient:
    """
    Dependency injection para RAGClient.
    
    Yields:
        RAGClient: Cliente configurado.
    """
    settings = get_settings()
    client = RAGClient(
        base_url=settings.rag_service_url,
        timeout=settings.rag_service_timeout,
    )
    try:
        yield client
    finally:
        await client.close()
```

---

## 📄 `app/services/processo_service.py`

```python
"""
Service de Processos — Lógica de negócio.

Encapsula regras de negócio, validações e orquestração.
Desacoplado de FastAPI (sem depends).

Padrão: Todos métodos recebem db.Session e retornam models/DTOs.
"""

import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.documento import Documento
from app.models.processo import Processo, StatusEnum
from app.models.usuario import Usuario
from app.services.rag_client import RAGClient


class ProcessoService:
    """Service para operações de processos."""
    
    UPLOAD_DIR = Path("uploads")
    
    @classmethod
    def _get_upload_path(cls, processo_id: str, tipo_doc: str) -> Path:
        """
        Retorna path onde o documento será salvo.
        
        Args:
            processo_id: ID do processo.
            tipo_doc: Tipo de documento.
            
        Returns:
            Path: Path relativo do arquivo.
        """
        dir_path = cls.UPLOAD_DIR / processo_id
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo: tipo_doc_timestamp.pdf
        timestamp = uuid4().hex[:8]
        filename = f"{tipo_doc}_{timestamp}.pdf"
        
        return dir_path / filename
    
    @staticmethod
    async def criar_processo(
        db: AsyncSession,
        usuario: Usuario,
        tipo: str,
    ) -> Processo:
        """
        Cria novo processo.
        
        Args:
            db: Session de banco.
            usuario: Usuário (professor) criador.
            tipo: Tipo de processo.
            
        Returns:
            Processo: Processo criado.
        """
        # Gera número único: CPPD-XXX/2026
        # Em produção, usar sequence do DB ou service dedicado
        numero = f"CPPD-{uuid4().hex[:3].upper()}/2026"
        
        processo = Processo(
            numero=numero,
            usuario_id=usuario.id,
            tipo=tipo,
            status=StatusEnum.AGUARDANDO_ANALISE,
        )
        
        db.add(processo)
        await db.flush()
        
        return processo
    
    @staticmethod
    async def listar_processos(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Processo]:
        """
        Lista todos os processos (para avaliador).
        
        Args:
            db: Session de banco.
            skip: Offset de paginação.
            limit: Limite de resultados.
            
        Returns:
            list[Processo]: Processos paginados.
        """
        stmt = (
            select(Processo)
            .offset(skip)
            .limit(limit)
            .order_by(Processo.criado_em.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def listar_processos_usuario(
        db: AsyncSession,
        usuario_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Processo]:
        """
        Lista processos do usuário (professor).
        
        Args:
            db: Session de banco.
            usuario_id: ID do usuário.
            skip: Offset de paginação.
            limit: Limite de resultados.
            
        Returns:
            list[Processo]: Processos do usuário.
        """
        stmt = (
            select(Processo)
            .where(Processo.usuario_id == usuario_id)
            .offset(skip)
            .limit(limit)
            .order_by(Processo.criado_em.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_processo(
        db: AsyncSession,
        processo_id: str,
    ) -> Processo | None:
        """
        Obtém processo com documentos (eager load).
        
        Args:
            db: Session de banco.
            processo_id: ID do processo.
            
        Returns:
            Processo | None: Processo com documentos carregados.
        """
        stmt = (
            select(Processo)
            .where(Processo.id == processo_id)
            .options(selectinload(Processo.documentos))
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    
    @staticmethod
    async def salvar_documento(
        db: AsyncSession,
        processo_id: str,
        tipo_doc: str,
        arquivo_bytes: bytes,
        nome_arquivo: str,
    ) -> Documento:
        """
        Salva documento no disco e registra no DB.
        
        Args:
            db: Session de banco.
            processo_id: ID do processo.
            tipo_doc: Tipo de documento.
            arquivo_bytes: Conteúdo binário do arquivo.
            nome_arquivo: Nome original do arquivo.
            
        Returns:
            Documento: Documento criado.
        """
        # Salvar arquivo no disco
        caminho = ProcessoService._get_upload_path(processo_id, tipo_doc)
        with open(caminho, "wb") as f:
            f.write(arquivo_bytes)
        
        # Criar registro no BD
        documento = Documento(
            processo_id=processo_id,
            nome_arquivo=nome_arquivo,
            tipo_doc=tipo_doc,
            caminho_arquivo=str(caminho),
        )
        
        db.add(documento)
        await db.flush()
        
        return documento
    
    @staticmethod
    async def atualizar_status(
        db: AsyncSession,
        processo_id: str,
        novo_status: StatusEnum,
    ) -> Processo | None:
        """
        Atualiza status do processo.
        
        Args:
            db: Session de banco.
            processo_id: ID do processo.
            novo_status: Novo status.
            
        Returns:
            Processo | None: Processo atualizado.
        """
        stmt = select(Processo).where(Processo.id == processo_id)
        result = await db.execute(stmt)
        processo = result.scalars().first()
        
        if processo:
            processo.status = novo_status
            await db.flush()
        
        return processo
    
    @staticmethod
    async def salvar_despacho_automatico(
        db: AsyncSession,
        processo_id: str,
        despacho: str,
    ) -> Processo | None:
        """
        Salva despacho automático gerado pelo RAG.
        
        Args:
            db: Session de banco.
            processo_id: ID do processo.
            despacho: Texto do despacho.
            
        Returns:
            Processo | None: Processo atualizado.
        """
        stmt = select(Processo).where(Processo.id == processo_id)
        result = await db.execute(stmt)
        processo = result.scalars().first()
        
        if processo:
            processo.despacho_automatico = despacho
            await db.flush()
        
        return processo
    
    @staticmethod
    async def get_documentos_texto_concatenado(
        db: AsyncSession,
        processo_id: str,
    ) -> str:
        """
        Concatena conteúdo de todos os documentos para análise.
        
        Args:
            db: Session de banco.
            processo_id: ID do processo.
            
        Returns:
            str: Texto concatenado dos documentos.
        """
        stmt = select(Documento).where(Documento.processo_id == processo_id)
        result = await db.execute(stmt)
        documentos = result.scalars().all()
        
        textos = [
            f"[{d.tipo_doc}]\n{d.conteudo_extraido or ''}"
            for d in documentos
        ]
        
        return "\n\n".join(textos)
```

---

# FASE 5 — ROTAS (Endpoints)

## 📄 `app/routers/__init__.py`

```python
"""
Routers FastAPI.

Expõe todos os routers para inclusão em main.py.
"""

from app.routers.analise import router as router_analise
from app.routers.auth import router as router_auth
from app.routers.processos import router as router_processos

__all__ = [
    "router_auth",
    "router_processos",
    "router_analise",
]
```

---

## 📄 `app/routers/auth.py`

```python
"""
Rotas de autenticação.

Endpoints:
- POST /api/v1/auth/register — Registro de novo usuário
- POST /api/v1/auth/login — Login (retorna JWT)
- GET /api/v1/auth/me — Dados do usuário logado
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.usuario import Usuario
from app.schemas.auth import TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Registra novo usuário.
    
    Args:
        user_data: Dados do usuário (nome, email, senha, role).
        db: Sessão de banco.
        
    Returns:
        UserResponse: Usuário criado (sem senha).
        
    Raises:
        HTTPException: Se email já existe.
    """
    # Verifica se email já existe
    stmt = select(Usuario).where(Usuario.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado.",
        )
    
    # Cria novo usuário
    novo_usuario = Usuario(
        nome=user_data.nome,
        email=user_data.email,
        senha_hash=hash_password(user_data.senha),
        role=user_data.role,
        setor=user_data.setor,
    )
    
    db.add(novo_usuario)
    await db.commit()
    await db.refresh(novo_usuario)
    
    return novo_usuario


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    """
    Login de usuário (retorna JWT).
    
    Args:
        form_data: Credenciais (username [email], password).
        db: Sessão de banco.
        
    Returns:
        TokenResponse: Token JWT.
        
    Raises:
        HTTPException: Se credenciais inválidas.
    """
    # Busca usuário por email
    stmt = select(Usuario).where(Usuario.email == form_data.username)
    result = await db.execute(stmt)
    usuario = result.scalars().first()
    
    if not usuario or not verify_password(form_data.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos.",
        )
    
    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
        )
    
    # Cria token
    access_token_expires = timedelta(hours=1)
    access_token = create_access_token(
        data={"sub": str(usuario.id)},
        expires_delta=access_token_expires,
    )
    
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna dados do usuário logado.
    
    Args:
        token: JWT do header Authorization.
        db: Sessão de banco.
        
    Returns:
        UserResponse: Dados do usuário.
    """
    from app.core.dependencies import get_current_user
    
    user = await get_current_user(token, db)
    return user
```

---

## 📄 `app/routers/processos.py`

```python
"""
Rotas de processos.

Endpoints:
- POST /api/v1/processos — Cria novo processo
- GET /api/v1/processos — Lista todos (avaliador)
- GET /api/v1/processos/meus — Lista do professor
- GET /api/v1/processos/{id} — Detalhes com documentos
- PATCH /api/v1/processos/{id}/status — Atualiza status
- POST /api/v1/processos/{id}/documentos — Upload de PDFs
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.usuario import Usuario
from app.schemas.processo import (
    ProcessoCreate,
    ProcessoResponse,
    ProcessoResumo,
)
from app.services.processo_service import ProcessoService
from app.services.rag_client import RAGClient, get_rag_client

router = APIRouter(prefix="/api/v1/processos", tags=["processos"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.post("", response_model=ProcessoResponse)
async def criar_processo(
    processo_data: ProcessoCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Cria novo processo (professor).
    
    Args:
        processo_data: Tipo de processo.
        token: JWT.
        db: Sessão de banco.
        
    Returns:
        ProcessoResponse: Processo criado.
    """
    usuario = await get_current_user(token, db)
    
    processo = await ProcessoService.criar_processo(
        db=db,
        usuario=usuario,
        tipo=processo_data.tipo,
    )
    
    await db.commit()
    
    return ProcessoResponse.from_orm(processo)


@router.get("", response_model=list[ProcessoResumo])
async def listar_processos(
    skip: int = 0,
    limit: int = 50,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
):
    """
    Lista todos os processos (avaliador).
    
    Args:
        skip: Offset de paginação.
        limit: Limite de resultados.
        
    Returns:
        list[ProcessoResumo]: Processos resumidos.
    """
    # Opcional: require_role("avaliador")
    processos = await ProcessoService.listar_processos(
        db=db,
        skip=skip,
        limit=limit,
    )
    
    return [ProcessoResumo.from_orm(p) for p in processos]


@router.get("/meus", response_model=list[ProcessoResumo])
async def listar_meus_processos(
    skip: int = 0,
    limit: int = 50,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
):
    """
    Lista processos do professor logado.
    
    Args:
        skip: Offset de paginação.
        limit: Limite de resultados.
        
    Returns:
        list[ProcessoResumo]: Processos do usuário.
    """
    usuario = await get_current_user(token, db)
    
    processos = await ProcessoService.listar_processos_usuario(
        db=db,
        usuario_id=usuario.id,
        skip=skip,
        limit=limit,
    )
    
    return [ProcessoResumo.from_orm(p) for p in processos]


@router.get("/{processo_id}", response_model=ProcessoResponse)
async def get_processo(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
):
    """
    Obtém detalhes de um processo.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        ProcessoResponse: Processo com documentos.
        
    Raises:
        HTTPException: Se processo não existe.
    """
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    return ProcessoResponse.from_orm(processo)


@router.post("/{processo_id}/documentos")
async def upload_documentos(
    processo_id: str,
    arquivos: list[UploadFile] = File(...),
    tipos_doc: list[str] = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
    rag_client: RAGClient = Depends(get_rag_client),
):
    """
    Upload de múltiplos documentos para um processo.
    
    Após upload, dispara background task para verificar conformidade via RAG.
    
    Args:
        processo_id: ID do processo.
        arquivos: Lista de arquivos (multipart/form-data).
        tipos_doc: Lista de tipos (requerimento, cpf, etc.) em mesmo ordem.
        background_tasks: Task runner.
        
    Returns:
        dict: {"sucesso": int, "falhas": int}
    """
    usuario = await get_current_user(token, db)
    
    # Valida processo existe e pertence ao usuário
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo or processo.usuario_id != usuario.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado.",
        )
    
    if len(arquivos) != len(tipos_doc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Número de arquivos não coincide com tipos.",
        )
    
    sucesso = 0
    for arquivo, tipo_doc in zip(arquivos, tipos_doc):
        try:
            conteudo = await arquivo.read()
            await ProcessoService.salvar_documento(
                db=db,
                processo_id=processo_id,
                tipo_doc=tipo_doc,
                arquivo_bytes=conteudo,
                nome_arquivo=arquivo.filename,
            )
            sucesso += 1
        except Exception as e:
            print(f"Erro salvando {arquivo.filename}: {e}")
    
    await db.commit()
    
    # Dispara background task: verificar conformidade
    background_tasks.add_task(
        _verificar_conformidade_background,
        db=db,
        processo_id=processo_id,
        rag_client=rag_client,
    )
    
    return {"sucesso": sucesso, "falhas": len(arquivos) - sucesso}


@router.patch("/{processo_id}/status")
async def atualizar_status_processo(
    processo_id: str,
    novo_status: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
):
    """
    Atualiza status do processo (avaliador).
    
    Args:
        processo_id: ID do processo.
        novo_status: Novo status.
        
    Returns:
        ProcessoResponse: Processo atualizado.
    """
    from app.models.processo import StatusEnum
    
    try:
        status_enum = StatusEnum(novo_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status inválido: {novo_status}",
        )
    
    processo = await ProcessoService.atualizar_status(
        db=db,
        processo_id=processo_id,
        novo_status=status_enum,
    )
    
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    await db.commit()
    
    return ProcessoResponse.from_orm(processo)


# Background task (executada após request retornar)
async def _verificar_conformidade_background(
    db: AsyncSession,
    processo_id: str,
    rag_client: RAGClient,
):
    """
    Background task: verifica conformidade via RAG após upload.
    
    Se conformidade < 100%: status → pendente_professor
    Se conformidade == 100%: status → analise_pendente
    """
    try:
        from app.models.processo import StatusEnum
        
        # Busca texto concatenado
        texto = await ProcessoService.get_documentos_texto_concatenado(
            db=db,
            processo_id=processo_id,
        )
        
        if not texto:
            return
        
        # Chama RAG
        resultado = await rag_client.verificar_conformidade(
            texto_documento=texto,
            tipo_processo="progressao_funcional",  # TODO: pegar tipo real
        )
        
        conformidade = resultado.get("conformidade_pct", 0)
        pendencias = resultado.get("pendencias", [])
        
        if conformidade < 100:
            # Gera despacho de devolução
            despacho = await rag_client.sugerir_despacho(
                texto_documento=texto,
                pendencias=", ".join(pendencias),
            )
            
            await ProcessoService.salvar_despacho_automatico(
                db=db,
                processo_id=processo_id,
                despacho=despacho.get("despacho", ""),
            )
            
            await ProcessoService.atualizar_status(
                db=db,
                processo_id=processo_id,
                novo_status=StatusEnum.PENDENTE_PROFESSOR,
            )
        else:
            await ProcessoService.atualizar_status(
                db=db,
                processo_id=processo_id,
                novo_status=StatusEnum.ANALISE_PENDENTE,
            )
        
        await db.commit()
    except Exception as e:
        print(f"Erro em background task: {e}")
```

---

## 📄 `app/routers/analise.py`

```python
"""
Rotas de análise — Orquestração entre Backend e RAG.

Endpoints:
- GET /api/v1/analise/{id}/resumo — Resumo do processo
- GET /api/v1/analise/{id}/conformidade — Conformidade
- POST /api/v1/analise/{id}/despacho — Gerar despacho
- POST /api/v1/analise/{id}/aprovar-despacho — Aprovar despacho
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.processo_service import ProcessoService
from app.services.rag_client import RAGClient, get_rag_client

router = APIRouter(prefix="/api/v1/analise", tags=["analise"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("/{processo_id}/resumo")
async def get_resumo(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
    rag_client: RAGClient = Depends(get_rag_client) = None,
):
    """
    Gera resumo do processo via RAG.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        dict: {"resumo": str, "palavras_chave": list[str]}
    """
    usuario = await get_current_user(token, db)
    
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    texto = await ProcessoService.get_documentos_texto_concatenado(
        db=db,
        processo_id=processo_id,
    )
    
    if not texto:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum documento disponível.",
        )
    
    resultado = await rag_client.gerar_resumo(texto_documento=texto)
    return resultado


@router.get("/{processo_id}/conformidade")
async def get_conformidade(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
    rag_client: RAGClient = Depends(get_rag_client) = None,
):
    """
    Verifica conformidade do processo.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        dict: {"conformidade_pct": float, "pendencias": list[str]}
    """
    usuario = await get_current_user(token, db)
    
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    texto = await ProcessoService.get_documentos_texto_concatenado(
        db=db,
        processo_id=processo_id,
    )
    
    resultado = await rag_client.verificar_conformidade(
        texto_documento=texto,
        tipo_processo=processo.tipo,
    )
    return resultado


@router.post("/{processo_id}/despacho")
async def gerar_despacho(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
    rag_client: RAGClient = Depends(get_rag_client) = None,
):
    """
    Gera sugestão de despacho via RAG.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        dict: {"despacho": str, "motivo": str}
    """
    usuario = await get_current_user(token, db)
    
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    texto = await ProcessoService.get_documentos_texto_concatenado(
        db=db,
        processo_id=processo_id,
    )
    
    resultado = await rag_client.sugerir_despacho(
        texto_documento=texto,
        pendencias="",  # TODO: passar pendências reais
    )
    return resultado


@router.post("/{processo_id}/aprovar-despacho")
async def aprovar_despacho(
    processo_id: str,
    despacho_editado: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db) = None,
):
    """
    Aprova/edita despacho e marca processo como concluído.
    
    Args:
        processo_id: ID do processo.
        despacho_editado: Texto do despacho (pode ser editado).
        
    Returns:
        dict: {"status": "concluido"}
    """
    from app.models.processo import StatusEnum
    
    usuario = await get_current_user(token, db)
    
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    # Salva despacho e muda status
    processo.despacho_avaliador = despacho_editado
    await ProcessoService.atualizar_status(
        db=db,
        processo_id=processo_id,
        novo_status=StatusEnum.CONCLUIDO,
    )
    
    await db.commit()
    
    return {"status": "concluido"}
```

---

# FASE 6 — ENTRYPOINT

## 📄 `app/main.py`

```python
"""
FastAPI application entrypoint.

Configura:
- CORS
- Database lifecycle
- Routers
- Exception handlers
- Middleware
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.database import close_db, init_db
from app.routers import router_analise, router_auth, router_processos


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle context manager para startup/shutdown.
    
    Startup: Inicializa database.
    Shutdown: Fecha conexões.
    """
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """
    Factory para criar aplicação FastAPI.
    
    Returns:
        FastAPI: Aplicação configurada.
    """
    settings = get_settings()
    
    app = FastAPI(
        title="ClarIA Backend",
        description="Backend do sistema ClarIA - Análise de Processos",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Frontend Vite dev
            "http://localhost:3000",  # Fallback
        ] if settings.environment == "development" else ["https://claria.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Routers
    app.include_router(router_auth)
    app.include_router(router_processos)
    app.include_router(router_analise)
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "environment": settings.environment}
    
    return app


# Instância global
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
```

---

# FASE 7 — MIGRATIONS (Alembic)

## 📄 `alembic/env.py` (Parcial de atualização)

```python
"""
Configuração de migrations Alembic para modo async.

IMPORTANTE: Este é um exemplo. Merge com seu env.py existente.
"""

# ... código existente ...

from sqlalchemy.ext.asyncio import create_async_engine

from app.models.usuario import Base  # Importar Base dos modelos

# ... código existente ...

# Para autogenerate funcionar, adicione:
target_metadata = Base.metadata


# ... resto do código ...
```

---

# FASE 8 — SCRIPTS

## 📄 `scripts/seed_usuarios.py`

```python
"""
Script para seed de usuários de teste.

Uso: python scripts/seed_usuarios.py
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.core.security import hash_password
from app.models.usuario import Usuario


async def seed_usuarios():
    """Cria usuários de teste."""
    settings = get_settings()
    
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as session:
        # Usuários de teste
        usuarios_teste = [
            {
                "nome": "Professor Teste",
                "email": "professor@uespi.br",
                "senha": "123456",
                "role": "professor",
                "setor": "PROEN",
            },
            {
                "nome": "Avaliador Teste",
                "email": "avaliador@uespi.br",
                "senha": "123456",
                "role": "avaliador",
                "setor": "Reitoria",
            },
        ]
        
        for dados in usuarios_teste:
            usuario = Usuario(
                nome=dados["nome"],
                email=dados["email"],
                senha_hash=hash_password(dados["senha"]),
                role=dados["role"],
                setor=dados["setor"],
            )
            session.add(usuario)
            print(f"✅ Usuário criado: {dados['email']}")
        
        await session.commit()
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_usuarios())
```

---

# FASE 9 — DOCKER

## 📄 `docker-compose.yaml` (Atualizado)

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    container_name: claria_db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-claria_db}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: .
    container_name: claria_backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-claria_db}
      SECRET_KEY: ${SECRET_KEY:-your-secret-key-change-in-production}
      RAG_SERVICE_URL: ${RAG_SERVICE_URL:-http://localhost:8001}
      ENVIRONMENT: ${ENVIRONMENT:-development}
      DEBUG: ${DEBUG:-true}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app
      - uploads:/app/uploads
    networks:
      - claria_network

volumes:
  postgres_data:
  uploads:

networks:
  claria_network:
    driver: bridge
```

---

## 📄 `Dockerfile` (Atualizado)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Expose porta
EXPOSE 8000

# Comando padrão
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

# RESUMO

## ✅ Estrutura Final

```
app/
├── __init__.py
├── main.py                    # Entrypoint FastAPI
├── config.py                  # Configurações Pydantic
├── core/
│   ├── __init__.py
│   ├── database.py           # SQLAlchemy async
│   ├── security.py           # JWT + bcrypt
│   └── dependencies.py       # Dependency injection
├── models/
│   ├── __init__.py
│   ├── usuario.py            # ORM Usuario
│   ├── processo.py           # ORM Processo
│   └── documento.py          # ORM Documento
├── schemas/
│   ├── __init__.py
│   ├── auth.py               # Pydantic schemas auth
│   ├── processo.py           # Pydantic schemas processo
│   └── documento.py          # Pydantic schemas documento
├── services/
│   ├── __init__.py
│   ├── rag_client.py         # Client HTTP RAG
│   └── processo_service.py   # Lógica de negócio
└── routers/
    ├── __init__.py
    ├── auth.py               # /api/v1/auth
    ├── processos.py          # /api/v1/processos
    └── analise.py            # /api/v1/analise

scripts/
└── seed_usuarios.py          # Script de seed

alembic/
├── env.py                    # Config Alembic async
├── versions/
└── alembic.ini

.env.example                  # Variáveis de ambiente
requirements.txt              # Dependências Python
docker-compose.yaml           # Orquestração Docker
Dockerfile                    # Image Docker
```

## 🔗 Fluxo de Dados

1. **Frontend** faz POST `/api/v1/auth/login` → Recebe JWT
2. **Frontend** faz POST `/api/v1/processos` com JWT → Backend cria processo
3. **Professor** faz POST `/api/v1/processos/{id}/documentos` com PDFs
4. **Backend** (background task) chama `/ia/conformidade` do RAG
5. **RAG** analisa documentos, retorna conformidade %
6. **Backend** atualiza status do processo e salva despacho automático
7. **Avaliador** consulta GET `/api/v1/processos` → vê processos prontos
8. **Avaliador** faz GET `/api/v1/analise/{id}/resumo` → Backend chama RAG, retorna resumo
9. **Avaliador** faz POST `/api/v1/analise/{id}/despacho` → Backend retorna sugestão
10. **Avaliador** faz POST `/api/v1/analise/{id}/aprovar-despacho` → Processo concluído

## 🚀 Próximos Passos

1. Criar migration inicial: `alembic revision --autogenerate -m "create_initial_tables"`
2. Rodar migration: `alembic upgrade head`
3. Executar seed: `python scripts/seed_usuarios.py`
4. Testar health check: `curl http://localhost:8000/health`
5. Testar login: `curl -X POST http://localhost:8000/api/v1/auth/login ...`

---

**FIM DO DOCUMENTO**
