"""Configuração de conexão com o banco de dados.

Módulo responsável por inicializar a conexão SQLAlchemy
e gerenciar as sessões do banco de dados.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import settings

# Criar engine de conexão
engine = create_engine(
    settings.database_url,
    echo=False,  # Mudar para True em desenvolvimento se necessário
)

# Factory para criar sessões
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base para modelos ORM
Base = declarative_base()


def get_database_session():
    """Obter sessão do banco de dados.

    Yields:
        SessionLocal: Sessão ativa do banco de dados.
    """
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()