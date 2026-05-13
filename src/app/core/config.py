"""
Configuração centralizada da aplicação.

Carrega e valida variáveis de ambiente usando dotenv.
"""

import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente apenas uma vez
load_dotenv()


class Settings:
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

    # Segurança
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sua-chave-secreta-muito-segura-aqui")

    @property
    def database_url(self) -> str:
        """
        Constrói a URL de conexão com o banco de dados.

        Returns:
            str: URL de conexão PostgreSQL formatada.
        """
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
