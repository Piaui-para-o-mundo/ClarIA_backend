from app.api.routes.analise import router as router_analise
from app.api.routes.auth import router as router_auth
from app.api.routes.dispatch import router as router_dispatch
from app.api.routes.processos import router as router_processos

__all__ = [
    'router_auth',
    'router_processos',
    'router_analise',
    'router_dispatch',
]
