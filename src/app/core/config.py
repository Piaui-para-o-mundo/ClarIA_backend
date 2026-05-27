"""
Configuração centralizada da aplicação.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

   
    app_name: str = "ClarIA"

    
    postgres_user: str | None = Field(default=None, alias="POSTGRES_USER")
    postgres_password: str | None = Field(default=None, alias="POSTGRES_PASSWORD")
    postgres_db: str | None = Field(default=None, alias="POSTGRES_DB")

    database_url: str = Field(alias="DATABASE_URL")

    api_port: int = Field(default=8000, alias="API_PORT")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")

   
    secret_key: str = Field(alias="SECRET_KEY")

    algorithm: str = Field(
        default="HS256",
        alias="ALGORITHM",
    )

    access_token_expire_minutes: int = Field(
        default=60,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    
    rag_service_url: str = Field(
        default="http://localhost:8001",
        alias="RAG_SERVICE_URL",
    )

    rag_service_timeout: int = Field(
        default=120,
        alias="RAG_SERVICE_TIMEOUT",
    )

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )

    debug: bool = Field(default=False, alias="DEBUG")


@lru_cache
def get_settings() -> Settings:
    """Retorna as configurações da aplicação."""
    return Settings()