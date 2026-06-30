import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging() -> logging.Logger:
    """
    Configure structured rotating logging for ElevenBoss.
    Sets up both a console output stream and a rotating file log.
    
    Returns:
        logging.Logger: The configured 'discord' logger.
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure root/discord loggers
    logger = logging.getLogger("discord")
    logger.setLevel(logging.INFO)

    # Format for logs
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{"
    )

    # Console Handler for real-time monitoring
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Rotating File Handler (Max 5MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "bot.log"),
        encoding="utf-8",
        maxBytes=5 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Configure a custom application logger for project logic as well
    app_logger = logging.getLogger("elevenboss")
    app_logger.setLevel(logging.DEBUG)
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)
    app_logger.propagate = False # Prevent double-logging to root discord handlers

    return logger
