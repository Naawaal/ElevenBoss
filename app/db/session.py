import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.db.engine import get_engine

logger = logging.getLogger("app.db.session")

_sessionmaker: async_sessionmaker[AsyncSession] | None = None

def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """
    Exposes and lazily creates the async_sessionmaker bound to the Async Engine.
    """
    global _sessionmaker
    if _sessionmaker is not None:
        return _sessionmaker

    engine = get_engine()
    _sessionmaker = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
    return _sessionmaker

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager that provides a fresh, isolated AsyncSession for database operations.
    Handles commit, rollback, and cleanup lifecycles.
    
    Yields:
        AsyncSession: The transaction-isolated session.
    """
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            if isinstance(e, ValueError):
                logger.warning(f"Database transaction rolled back due to validation: {e}")
            else:
                logger.error(f"Database transaction error: {e}", exc_info=e)
            raise e
