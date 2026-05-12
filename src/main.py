"""Aplicação FastAPI principal.

Ponto de entrada da API, configuração inicial e roteamento.
"""

from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title="ClarIA Backend",
    description="API backend para ClarIA",
    version="1.0.0",
)


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