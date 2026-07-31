# apps/discord_bot/core/sentry_setup.py
"""Optional Sentry init (050). No-op without SENTRY_DSN; never attach secrets."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        from apps.discord_bot.core.instance_id import get_instance_id

        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("ENVIRONMENT", "development"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
            send_default_pii=False,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
        )
        sentry_sdk.set_tag("instance_id", get_instance_id())
        logger.info("Sentry initialized instance_id=%s", get_instance_id())
        return True
    except Exception:
        logger.exception("Sentry init failed — continuing without Sentry")
        return False


def set_command_context(
    *,
    command: str | None = None,
    hub: str | None = None,
    guild_id: int | None = None,
    rpc_name: str | None = None,
    latency_class: str | None = None,
    error_category: str | None = None,
) -> None:
    try:
        import sentry_sdk
    except ImportError:
        return
    if command:
        sentry_sdk.set_tag("command", command)
    if hub:
        sentry_sdk.set_tag("hub", hub)
    if guild_id is not None:
        sentry_sdk.set_tag("guild_id", str(guild_id))
    if rpc_name:
        sentry_sdk.set_tag("rpc_name", rpc_name)
    if latency_class:
        sentry_sdk.set_tag("latency_class", latency_class)
    if error_category:
        sentry_sdk.set_tag("error_category", error_category)
