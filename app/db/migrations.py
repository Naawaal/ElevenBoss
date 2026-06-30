import logging
import os
from alembic.config import Config
from alembic import command
from app.config import config
from app.error_reporting import capture_exception

logger = logging.getLogger("app.db.migrations")

def run_migrations() -> None:
    """
    Programmatically executes any pending Alembic migrations on bot startup.
    Ensures the database schema is updated to the latest revision ('head').
    Safely logs and reports failures instead of crashing the bot.
    """
    if not config.DATABASE_URL:
        logger.info("DATABASE_URL is not configured. Skipping automatic migrations.")
        return

    ini_path = "alembic.ini"
    if not os.path.exists(ini_path):
        logger.warning(f"alembic.ini was not found at {ini_path}. Skipping automatic migrations.")
        return

    try:
        logger.info("Running automatic database migrations...")
        
        # Instantiate Alembic configuration
        alembic_cfg = Config(ini_path)
        
        # Run upgrade to the latest head
        command.upgrade(alembic_cfg, "head")
        
        logger.info("Database migrations applied successfully.")
    except Exception as e:
        logger.critical(f"Failed to run automatic database migrations: {e}", exc_info=e)
        capture_exception(e)
