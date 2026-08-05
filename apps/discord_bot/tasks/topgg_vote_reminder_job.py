# apps/discord_bot/tasks/topgg_vote_reminder_job.py
"""APScheduler job for Top.gg vote DM reminders (Feature 055)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import discord
from discord.ext import commands

from apps.discord_bot.core.topgg_vote import (
    VoteCheckResult,
    check_topgg_vote,
    resolve_topgg_bot_id,
    topgg_vote_url,
)
from apps.discord_bot.db.client import get_client

logger = logging.getLogger(__name__)


def build_vote_reminder_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⭐ Ready to vote again?",
        description=(
            "Your Top.gg vote is available again whenever you’re ready.\n\n"
            "Voting helps more managers discover ElevenBoss, and you can "
            "claim your vote reward from the Store afterward."
        ),
        color=0xF1C40F,  # Gold
    )
    embed.set_footer(text="Just one reminder for this vote window.")
    return embed


class VoteReminderView(discord.ui.View):
    def __init__(self, vote_url: str) -> None:
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Vote on Top.gg", url=vote_url, style=discord.ButtonStyle.link))


async def run_topgg_vote_reminders(bot: commands.Bot) -> None:
    """30-minute periodic job: claim due reminder rows, re-verify with Top.gg, and send DM reminders."""
    enabled_env = os.environ.get("TOPGG_VOTE_REMINDERS_ENABLED", "true").strip().lower()
    if enabled_env not in ("true", "1", "yes"):
        logger.info("run_topgg_vote_reminders skipped — disabled via TOPGG_VOTE_REMINDERS_ENABLED env")
        return

    db = await get_client()

    # Check database game_config override
    try:
        cfg_res = await db.table("game_config").select("value_json").eq("key", "topgg_vote_reminders_enabled").maybe_single().execute()
        if cfg_res and cfg_res.data:
            val = cfg_res.data.get("value_json")
            if val is False or str(val).lower() in ("false", "0"):
                logger.info("run_topgg_vote_reminders skipped — disabled via game_config")
                return
    except Exception:
        logger.debug("Failed to read topgg_vote_reminders_enabled config; continuing", exc_info=True)

    token = os.environ.get("TOPGG_TOKEN", "")
    bot_id = resolve_topgg_bot_id(bot.user.id if bot.user else None)
    vote_url_str = topgg_vote_url(runtime_bot_id=bot.user.id if bot.user else None)

    try:
        res = await db.rpc("claim_due_topgg_vote_reminders", {"p_limit": 100}).execute()
        rows = res.data or []
    except Exception:
        logger.exception("Failed to claim due topgg vote reminders")
        return

    if not rows:
        return

    logger.info("Claimed %d due topgg vote reminder(s) for verification", len(rows))
    now = datetime.now(timezone.utc)
    circuit_breaker = False

    for row in rows:
        user_id = int(row["discord_user_id"])
        fail_count = int(row.get("check_failure_count") or 0)

        if circuit_breaker:
            # Skip Top.gg API call, release claim with 30m backoff
            await _defer_reminder_row(db, user_id, fail_count + 1, now + timedelta(minutes=30))
            continue

        # Re-verify vote status
        try:
            vote_result = await check_topgg_vote(
                discord_user_id=user_id,
                token=token,
                bot_id=bot_id,
            )
        except Exception:
            vote_result = VoteCheckResult(status="unavailable")

        if vote_result.status == "voted":
            # User voted again! Update reminder window
            next_v = vote_result.next_vote_at or (now + timedelta(hours=12))
            iso_next = next_v.isoformat()
            window_key = f"{user_id}:{iso_next}"
            try:
                await db.table("topgg_vote_reminders").update({
                    "last_vote_at": (vote_result.vote_at or now).isoformat(),
                    "next_vote_at": iso_next,
                    "reminder_window_key": window_key,
                    "reminder_claimed_at": None,
                    "reminder_sent_at": None,
                    "dm_status": None,
                    "fallback_pending": False,
                    "last_checked_at": now.isoformat(),
                    "next_check_at": iso_next,
                    "check_failure_count": 0,
                    "updated_at": now.isoformat(),
                }).eq("discord_user_id", user_id).execute()
            except Exception:
                logger.exception("Failed to update reminder window for user %s", user_id)
            continue

        if vote_result.status == "unavailable":
            # API failure or rate limit — apply backoff (30m, 60m, 2h)
            new_fails = fail_count + 1
            if new_fails == 1:
                delay = timedelta(minutes=30)
            elif new_fails == 2:
                delay = timedelta(minutes=60)
            else:
                delay = timedelta(hours=2)
                circuit_breaker = True  # open circuit breaker for remaining batch

            await _defer_reminder_row(db, user_id, new_fails, now + delay)
            continue

        # status == "not_voted" -> User is eligible! Send DM.
        sent_ok = False
        dm_error_type = None

        user = bot.get_user(user_id)
        if user is None:
            try:
                user = await bot.fetch_user(user_id)
            except Exception as fetch_err:
                dm_error_type = type(fetch_err).__name__

        if user is not None:
            try:
                embed = build_vote_reminder_embed()
                view = VoteReminderView(vote_url_str)
                await user.send(embed=embed, view=view)
                sent_ok = True
            except discord.Forbidden:
                dm_error_type = "Forbidden"
            except Exception as send_err:
                dm_error_type = type(send_err).__name__

        # Update DB row outcome
        try:
            if sent_ok:
                await db.table("topgg_vote_reminders").update({
                    "reminder_claimed_at": None,
                    "reminder_sent_at": now.isoformat(),
                    "dm_status": "sent",
                    "fallback_pending": False,
                    "last_checked_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }).eq("discord_user_id", user_id).execute()
                logger.info("Sent Top.gg vote reminder DM to user %s", user_id)
            elif dm_error_type == "Forbidden":
                await db.table("topgg_vote_reminders").update({
                    "reminder_claimed_at": None,
                    "reminder_sent_at": now.isoformat(),
                    "dm_status": "forbidden",
                    "fallback_pending": True,
                    "fallback_created_at": now.isoformat(),
                    "last_checked_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }).eq("discord_user_id", user_id).execute()
                logger.info("Top.gg vote reminder DM forbidden for user %s; created fallback notice", user_id)
            else:
                # Transient failure — retry or fallback if fails >= 3
                new_fails = fail_count + 1
                if new_fails >= 3:
                    await db.table("topgg_vote_reminders").update({
                        "reminder_claimed_at": None,
                        "reminder_sent_at": now.isoformat(),
                        "dm_status": "failed",
                        "fallback_pending": True,
                        "fallback_created_at": now.isoformat(),
                        "last_checked_at": now.isoformat(),
                        "check_failure_count": new_fails,
                        "updated_at": now.isoformat(),
                    }).eq("discord_user_id", user_id).execute()
                    logger.warning("Top.gg vote reminder DM failed %d times for user %s (%s); created fallback notice", new_fails, user_id, dm_error_type)
                else:
                    await _defer_reminder_row(db, user_id, new_fails, now + timedelta(minutes=30))
        except Exception:
            logger.exception("Failed to update reminder outcome for user %s", user_id)


async def _defer_reminder_row(db: Any, user_id: int, failure_count: int, next_check: datetime) -> None:
    now = datetime.now(timezone.utc)
    try:
        await db.table("topgg_vote_reminders").update({
            "reminder_claimed_at": None,
            "last_checked_at": now.isoformat(),
            "next_check_at": next_check.isoformat(),
            "check_failure_count": failure_count,
            "updated_at": now.isoformat(),
        }).eq("discord_user_id", user_id).execute()
    except Exception:
        logger.exception("Failed to defer reminder row for user %s", user_id)
