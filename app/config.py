import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("app.config")

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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
    DATABASE_ECHO: bool = os.getenv("DATABASE_ECHO", "false").strip().lower() == "true"
    # Feature flag: enables the guided onboarding flow instead of the one-shot /register
    REGISTRATION_ONBOARDING_ENABLED: bool = os.getenv("REGISTRATION_ONBOARDING_ENABLED", "false").strip().lower() == "true"

    LEAGUE_RED_CARD_SUSPENSION_GAMES: int = 1

    DAILY_FITNESS_RECOVERY: int = 10
    DAILY_INJURED_FITNESS_RECOVERY: int = 5

    INJURY_SEVERITY_WEIGHTS: dict[str, int] = field(default_factory=lambda: {
        "minor_knock": 55,
        "strain": 30,
        "sprain": 12,
        "serious": 3,
    })

    INJURY_DURATION_DAYS: dict[str, tuple[int, int]] = field(default_factory=lambda: {
        "minor_knock": (1, 2),
        "strain": (2, 4),
        "sprain": (4, 7),
        "serious": (8, 14),
    })

    INJURY_FITNESS_PENALTY: dict[str, tuple[int, int]] = field(default_factory=lambda: {
        "minor_knock": (8, 15),
        "strain": (15, 25),
        "sprain": (20, 35),
        "serious": (35, 50),
    })

    FACILITY_MAX_LEVEL: int = 5

    FACILITY_UPGRADE_COSTS: dict[int, int] = field(default_factory=lambda: {
        1: 10_000,
        2: 35_000,
        3: 90_000,
        4: 200_000,
    })

    FACILITY_UPGRADE_DURATIONS_HOURS: dict[int, int] = field(default_factory=lambda: {
        1: 6,
        2: 12,
        3: 24,
        4: 48,
    })

    MEDICAL_CLINIC_INJURY_RECOVERY_BONUS: dict[int, int] = field(default_factory=lambda: {
        1: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    })

    TRAINING_PITCH_RECOVERY_BONUS: dict[int, int] = field(default_factory=lambda: {
        1: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    })

    STADIUM_CAPACITY_BY_LEVEL: dict[int, int] = field(default_factory=lambda: {
        1: 10_000,
        2: 15_000,
        3: 25_000,
        4: 40_000,
        5: 60_000,
    })

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

    # Warn if database is not configured
    if not config.DATABASE_URL:
        logger.warning("DATABASE_URL is not set — database features will be disabled.")

