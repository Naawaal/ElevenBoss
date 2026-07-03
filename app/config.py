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
        1: 250_000,
        2: 750_000,
        3: 1_600_000,
        4: 3_500_000,
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

    MANAGER_LEVEL_XP_THRESHOLDS: dict[int, int] = field(default_factory=lambda: {
        1: 0,
        2: 100,
        3: 240,
        4: 420,
        5: 650,
        6: 930,
        7: 1260,
        8: 1640,
        9: 2070,
        10: 2550,
        11: 3080,
        12: 3660,
        13: 4290,
        14: 4970,
        15: 5700,
        16: 6480,
        17: 7310,
        18: 8190,
        19: 9120,
        20: 10100,
        21: 11130,
        22: 12210,
        23: 13340,
        24: 14520,
        25: 15750,
        26: 17030,
        27: 18360,
        28: 19740,
        29: 21170,
        30: 22650,
        31: 24180,
        32: 25760,
        33: 27390,
        34: 29070,
        35: 30800,
        36: 32580,
    })

    FACILITY_MANAGER_LEVEL_REQUIREMENTS: dict[int, int] = field(default_factory=lambda: {
        2: 1,   # First upgrade: available immediately to new managers
        3: 4,   # Second tier: ~8 matches in
        4: 7,   # Third tier: ~23 matches in
        5: 10,  # Fourth tier: ~46 matches in
        6: 14,
        7: 18,
        8: 23,
        9: 29,
        10: 36,
    })

    MANAGER_XP_LEAGUE_PLAYED: int = 35
    MANAGER_XP_LEAGUE_WIN:    int = 20
    MANAGER_XP_LEAGUE_DRAW:   int = 10
    MANAGER_XP_LEAGUE_LOSS:   int =  5
    MANAGER_XP_CLEAN_SHEET:   int =  5
    MANAGER_XP_SCORED_3_PLUS: int =  5

    CLUB_REVENUE_LEAGUE_PLAYED: int = 35_000
    CLUB_REVENUE_LEAGUE_WIN:    int = 25_000
    CLUB_REVENUE_LEAGUE_DRAW:   int = 12_000
    CLUB_REVENUE_LEAGUE_LOSS:   int =  5_000
    CLUB_REVENUE_CLEAN_SHEET:   int =  8_000
    CLUB_REVENUE_SCORED_3_PLUS: int =  8_000
    CLUB_REVENUE_SPONSOR_BASE:  int = 15_000

    STADIUM_REVENUE_MULTIPLIER_BY_LEVEL: dict[int, float] = field(default_factory=lambda: {
        1: 1.00,
        2: 1.08,
        3: 1.16,
        4: 1.28,
        5: 1.42,
    })

    HQ_SPONSOR_REVENUE_MULTIPLIER_BY_LEVEL: dict[int, float] = field(default_factory=lambda: {
        1: 1.00,
        2: 1.05,
        3: 1.10,
        4: 1.18,
        5: 1.25,
    })

    CLUB_TREASURY_CAP_BASE:              int = 5_000_000
    CLUB_TREASURY_CAP_PER_MANAGER_LEVEL: int =   200_000
    CLUB_TREASURY_CAP_PER_HQ_LEVEL:      int = 1_000_000

    ECONOMY_SOURCE_LEAGUE_MATCH_REVENUE: str = "league_match_revenue"
    ECONOMY_SOURCE_FACILITY_UPGRADE_COST: str = "facility_upgrade_cost"

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

