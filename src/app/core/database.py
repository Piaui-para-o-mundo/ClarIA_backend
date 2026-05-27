
from typing import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

def get_engine() -> AsyncEngine:
    """
    Cria engine SQLAlchemy assincrono

    Returns:
        AsyncEngine: Engine SQLAlchemy para conexões assíncronas.
    """


    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
        pool_size=10,
        max_overflow=20,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """
    Factory para criar sessoes assincronas

    Args:
        engine: AsyncEngine configurado.

    Returns:
        async_sessionmaker: Factory para gerar sessões.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


async def init_db() -> None:
    """
    Inicializa database na startup da aplicação.

    Cria engine e session factory. Pode ser expandido para criar tabelas.
    """
    global _engine, _session_factory
    if _engine is None:
        _engine = get_engine()
    if _session_factory is None:
        _session_factory = get_session_factory(_engine)

    # Importa os modelos para registrar as tabelas no metadata antes do create_all.
    from app import models  # noqa: F401

    async with _engine.begin() as conn:
        from app.models.user import Base

        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_process_analysis_columns)


def _ensure_process_analysis_columns(sync_conn) -> None:
    """Adiciona colunas novas ao processo quando o schema já existe."""

    inspector = inspect(sync_conn)
    if "processos" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("processos")}
    dialect_name = sync_conn.dialect.name

    if dialect_name == "sqlite":
        timestamp_type = "DATETIME"
    else:
        timestamp_type = "TIMESTAMP WITH TIME ZONE"

    alter_statements = {
        "analise_status": "ALTER TABLE processos ADD COLUMN analise_status VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "analise_started_em": f"ALTER TABLE processos ADD COLUMN analise_started_em {timestamp_type}",
        "analise_concluida_em": f"ALTER TABLE processos ADD COLUMN analise_concluida_em {timestamp_type}",
        "analise_erro": "ALTER TABLE processos ADD COLUMN analise_erro TEXT",
        "analise_log": "ALTER TABLE processos ADD COLUMN analise_log TEXT",
        "resumo_ia": "ALTER TABLE processos ADD COLUMN resumo_ia TEXT",
        "checklist_ia": "ALTER TABLE processos ADD COLUMN checklist_ia TEXT",
    }

    for column_name, statement in alter_statements.items():
        if column_name not in existing_columns:
            sync_conn.execute(text(statement))

    if "analise_status" in existing_columns and dialect_name == "postgresql":
        sync_conn.execute(
            text(
                "ALTER TABLE processos ALTER COLUMN analise_status "
                "TYPE VARCHAR(20) USING analise_status::text"
            )
        )
        sync_conn.execute(
            text(
                "UPDATE processos "
                "SET analise_status = lower(analise_status) "
                "WHERE analise_status IS NOT NULL"
            )
        )
        sync_conn.execute(
            text(
                "ALTER TABLE processos ALTER COLUMN analise_status "
                "SET DEFAULT 'pending'"
            )
        )

async def close_db() -> None:
    """
    Fecha conexoes com database na shutdown da aplicação.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obter session de banco

    yields:
        AsyncSession: Session assincrona do banco
    """

    global _session_factory
    if not _session_factory:
        raise RuntimeError("Database nao foi inicializada. Chame init_db() na startup.")
    
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_session_factory_instance() -> async_sessionmaker:
    """Retorna a factory global de sessões já inicializada."""
    global _session_factory
    if not _session_factory:
        raise RuntimeError("Database nao foi inicializada. Chame init_db() na startup.")
    return _session_factory
            