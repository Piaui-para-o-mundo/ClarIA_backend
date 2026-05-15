
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    assync_sessionmaker,
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
    return assync_sessionmaker(
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
            