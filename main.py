"""
ElevenBoss Discord Bot — Entry Point
=====================================
Execution order:
  1. Load environment variables from .env
  2. Set up structured rotating logging
  3. Initialise Sentry (error tracking)
  4. Instantiate and run ElevenBossBot

Run:
    python main.py
"""

import os
import sys

import sentry_sdk
from dotenv import load_dotenv

from bot.core.logger import setup_logging
from bot.core.bot import ElevenBossBot

# ── 1. Environment ────────────────────────────────────────────
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SENTRY_DSN = os.getenv("SENTRY_DSN")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ── 2. Logging ────────────────────────────────────────────────
logger = setup_logging()

# ── 3. Sentry ─────────────────────────────────────────────────
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        # Capture 100% of transactions in dev; lower to 0.1–0.2 in heavy production
        traces_sample_rate=1.0 if ENVIRONMENT != "production" else 0.1,
        # Continuous profiling — lower in production to reduce overhead
        profiles_sample_rate=1.0 if ENVIRONMENT != "production" else 0.1,
        # Enrich every event with the release version if set
        release=os.getenv("RELEASE_VERSION"),
    )
    logger.info("Sentry initialised (environment=%s).", ENVIRONMENT)
else:
    logger.warning(
        "SENTRY_DSN not set — error tracking is DISABLED. "
        "Set it in .env for production deployments."
    )

# ── 4. Bot ────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        logger.critical(
            "DISCORD_TOKEN is missing from .env — bot cannot start."
        )
        sys.exit(1)

    bot = ElevenBossBot()

    # log_handler=None tells discord.py not to install its own handler
    # because we already configured one in setup_logging().
    bot.run(TOKEN, log_handler=None)
