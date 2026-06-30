import logging
from sqlalchemy import text
from app.db.session import get_session
from app.error_reporting import capture_exception

logger = logging.getLogger("app.db.health")

async def check_db_health() -> dict:
    """
    Runs a test query (SELECT 1) to verify database connectivity.
    Catches errors, logs the status, reports exceptions to Sentry, and returns
    a structured dictionary response.
    """
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            val = result.scalar()
            
            if val == 1:
                logger.info("Database health check passed.")
                return {"ok": True, "message": "Database connection healthy"}
            else:
                msg = f"Database health check returned unexpected scalar value: {val}"
                logger.error(msg)
                return {"ok": False, "message": msg}
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=e)
        capture_exception(e)
        return {"ok": False, "message": f"Database connection failed: {str(e)}"}
