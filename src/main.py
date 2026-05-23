"""Aplicação FastAPI principal.

Ponto de entrada da API, configuração inicial e roteamento.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.api.routes import auth, processos, analise


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

    app = FastAPI(
        title="ClarIA Backend",
        description="Backend do Sistema ClarIA - Analise de Processos",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://0.0.0.0:3000",
        "http://127.0.0.1:3000",
        "http://10.10.0.2:3000",
        "http://10.10.3.109:5173",
        "http://10.10.0.163:8007",
    ] if settings.environment == "development" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

    @app.get("/health")
    async def health_check():
        """Health check endpoint. """
        return {"status": "ok", "environment": settings.environment}

    # Rota raiz simples: redireciona para a documentação OpenAPI
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    # Evita 404 para favicon quando navegadores solicitarem
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    app.include_router(auth.router)
    app.include_router(processos.router)
    app.include_router(analise.router)

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