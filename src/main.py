"""Aplicação FastAPI principal.

Ponto de entrada da API, configuração inicial e roteamento.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.api.routes import auth, processos, analise, dispatch


def _sanitize_validation_payload(value: Any) -> Any:
    """Remove bytes brutos de erros de validação antes de serializar a resposta."""

    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<binary payload omitted>"

    if isinstance(value, dict):
        return {key: _sanitize_validation_payload(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_sanitize_validation_payload(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_sanitize_validation_payload(item) for item in value)

    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle context manager para startup/shutdown

    Startup: Inicializa o banco de dados.
    Shutdown: Fecha conexões do banco de dados.
    """

    await init_db()
    yield
    await close_db()

def create_app() -> FastAPI:
    """
    Factory para criar a aplicação FastAPI.

    Retorna:
        FastAPI: Instância da aplicação.
    """

    settings = get_settings()
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="ClarIA Backend",
        description="Backend do Sistema ClarIA - Analise de Processos",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Evita que erros de validação exponham corpos binários na resposta 422."""

        del request
        detail = _sanitize_validation_payload(jsonable_encoder(exc.errors()))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": detail},
        )

    # Configuração de CORS
    # Nota: allow_origins=["*"] não pode ser usado com allow_credentials=True
    if settings.environment == "development":
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8002",
            "http://localhost:8001",
            "http://127.0.0.1:8002",
            "http://0.0.0.0:8002",
            "http://0.0.0.0:8001",
            "http://0.0.0.0:5000",
            "http://0.0.0.0:5500",

        ]
        allow_credentials = True
    else:
        origins = ["*"]
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint. """
        return {"status": "ok", "environment": settings.environment}

    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    app.include_router(auth.router)
    app.include_router(processos.router)
    app.include_router(analise.router)
    app.include_router(dispatch.router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )