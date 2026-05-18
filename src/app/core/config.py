"""
Configuração centralizada da aplicação.

Carrega e valida variáveis de ambiente usando dotenv.
"""

import os
from dotenv import load_dotenv
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

# Carregar variáveis de ambiente apenas uma vez
load_dotenv()


class Settings(BaseSettings):
    """Configurações da aplicação com valores padrão."""

    # Banco de dados
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "appdb")

    # API
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")

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

    @property
    def database_url(self) -> str:
        """
        Constrói a URL de conexão com o banco de dados.

        Returns:
            str: URL de conexão PostgreSQL formatada.
        """
        env_database_url = os.getenv("DATABASE_URL")
        if env_database_url:
            return env_database_url

        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

@lru_cache
def get_settings() -> Settings:
    """Função para obter as configurações da aplicação com cache."""
    return Settings()
