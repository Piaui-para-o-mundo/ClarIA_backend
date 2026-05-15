"""Pacote `models` - modelos do domínio (ORM).

Adicionar modelos SQLAlchemy ou entidades aqui.
"""

from app.models.user import User


__all__ = ["User", "Processo", "Documento"]
