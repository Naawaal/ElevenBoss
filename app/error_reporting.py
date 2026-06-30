import logging
from typing import Optional
from app.config import config

logger = logging.getLogger("app.error_reporting")

_sentry_available = False

try:
    import sentry_sdk
    _sentry_available = True
except ImportError:
    logger.warning("sentry-sdk package not installed. Error reporting will run in no-op mode.")

def init_error_reporting() -> None:
    """
    Initialize the error reporting provider if configured.
    Safely degrades to a no-op mode if no provider is configured or available.
    """
    global _sentry_available
    if not _sentry_available:
        return

    dsn = config.SENTRY_DSN
    env = config.ENVIRONMENT

    if not dsn:
        logger.info("SENTRY_DSN is not configured. Running error reporting in no-op mode.")
        _sentry_available = False
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=env,
            traces_sample_rate=1.0 if env != "production" else 0.1,
            profiles_sample_rate=1.0 if env != "production" else 0.1,
        )
        logger.info(f"Sentry error reporting initialized (environment={env}).")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}", exc_info=e)
        _sentry_available = False

def capture_exception(error: Exception) -> None:
    """
    Capture an exception and send it to the configured error reporting provider.
    No-op if error reporting is disabled.
    """
    if _sentry_available:
        try:
            sentry_sdk.capture_exception(error)
        except Exception as e:
            # Avoid infinite loop in case logger also fails, but log to stderr
            logger.error(f"Failed to send exception to Sentry: {e}", exc_info=e)

def capture_message(message: str) -> None:
    """
    Capture a custom message and send it to the configured error reporting provider.
    No-op if error reporting is disabled.
    """
    if _sentry_available:
        try:
            sentry_sdk.capture_message(message)
        except Exception as e:
            logger.error(f"Failed to send message to Sentry: {e}", exc_info=e)
