"""Aplicação FastAPI principal.

Ponto de entrada da API, configuração inicial e roteamento.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes.auth import router as auth_router

app = FastAPI(
    title="ClarIA Backend",
    description="API backend para ClarIA",
    version="1.0.0",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origins permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Verificar saúde da aplicação.

    Returns:
        dict: Status da aplicação.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
    )