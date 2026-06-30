import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ConfigurationError(ValueError):
    """Raised when the bot configuration is invalid or missing required variables."""
    pass

@dataclass(frozen=True)
class Config:
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!").strip()
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "").strip()
    GUILD_ID: str = os.getenv("GUILD_ID", "").strip()

# Create a singleton config instance
config = Config()

def validate_config():
    """Validates the bot's configuration, raising ConfigurationError for critical failures."""
    if not config.DISCORD_TOKEN:
        raise ConfigurationError("DISCORD_TOKEN is missing from .env — execution halted.")

    # Validate LOG_LEVEL
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.LOG_LEVEL not in valid_levels:
        raise ConfigurationError(f"Invalid LOG_LEVEL '{config.LOG_LEVEL}'. Must be one of {valid_levels}")
