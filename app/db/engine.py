import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.engine.url import make_url
from app.config import config, ConfigurationError

logger = logging.getLogger("app.db.engine")

_engine: AsyncEngine | None = None

def get_engine() -> AsyncEngine:
    """
    Exposes and lazily instantiates the async SQLAlchemy engine.
    Safely logs the connection endpoint without printing credentials.
    Raises ConfigurationError if DATABASE_URL is not set.
    """
    global _engine
    if _engine is not None:
        return _engine

    if not config.DATABASE_URL:
        raise ConfigurationError(
            "DATABASE_URL is not set in environment configuration. Database features are disabled."
        )

    # Strip database credentials for security logging
    try:
        url_obj = make_url(config.DATABASE_URL)
        safe_url = f"{url_obj.drivername}://{url_obj.host}:{url_obj.port}/{url_obj.database}"
        logger.info(f"Initializing Async Database Engine: {safe_url}")
    except Exception:
        # Fallback if connection URL doesn't match standard patterns
        logger.info("Initializing Async Database Engine (custom connection string)")

    try:
        _engine = create_async_engine(
            config.DATABASE_URL,
            echo=config.DATABASE_ECHO,
            future=True,
            connect_args={"timeout": 30}
        )
        return _engine
    except Exception as e:
        logger.critical(f"Failed to initialize async database engine: {e}", exc_info=e)
        raise e
