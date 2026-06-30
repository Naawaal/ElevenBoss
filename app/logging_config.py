import os
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Configure structured rotating logging for ElevenBoss.
    Sets up a console output stream, an app.log for general execution logging,
    and an error.log specifically for warnings and errors.
    """
    # Ensure logs directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Get log level from configuration
    from app.config import config
    log_level_str = config.LOG_LEVEL
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Format for logs: Timestamps, log levels, module/logger names, and messages
    formatter = logging.Formatter(
        fmt="[{asctime}] [{levelname:<8}] {name}: {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate logging
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 1. Console Handler (for readable stdout during dev)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. General app.log Rotating Handler (keeps all logs from log_level and above)
    app_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8"
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    # 3. Dedicated error.log Rotating Handler (keeps WARNING and above)
    error_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "error.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Ensure discord logger uses the configured level
    logging.getLogger("discord").setLevel(log_level)

    # Capture unhandled exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Log to file and console
        root_logger.critical("Uncaught Exception occurred", exc_info=(exc_type, exc_value, exc_traceback))

        # Send to error reporting (import locally to avoid circular dependencies)
        try:
            from app.error_reporting import capture_exception
            capture_exception(exc_value)
        except Exception as e:
            root_logger.error(f"Error reporting failed to capture uncaught exception: {e}", exc_info=e)

    sys.excepthook = handle_exception
