# apps/discord_bot/core/pending_notices.py
"""Shared ephemeral pending notices helper (Feature 055)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import discord

from apps.discord_bot.core.topgg_vote import topgg_vote_url
from apps.discord_bot.tasks.topgg_vote_reminder_job import VoteReminderView

logger = logging.getLogger(__name__)


def build_pending_vote_notice_embed(runtime_bot_id: int | None = None) -> discord.Embed:
    embed = discord.Embed(
        title="⭐ Your Top.gg vote is available again",
        description=(
            "I couldn’t send the reminder by DM, so here’s a quick note.\n\n"
            "Vote whenever you’re ready, then return to the Store to claim your reward."
        ),
        color=0xF1C40F,
    )
    embed.set_footer(text="Just one reminder for this vote window.")
    return embed


async def maybe_send_pending_vote_notice(
    interaction: discord.Interaction,
    db: Any,
) -> bool:
    """Check if interaction user has a pending vote reminder fallback notice and send it ephemerally."""
    try:
        user_id = interaction.user.id
        now = datetime.now(timezone.utc)
        res = await db.table("topgg_vote_reminders") \
            .select("*") \
            .eq("discord_user_id", user_id) \
            .eq("fallback_pending", True) \
            .maybe_single() \
            .execute()

        row = res.data if res else None
        if not row:
            return False

        # If next_vote_at is in the future, user already voted again -> clear stale fallback
        next_v_str = row.get("next_vote_at")
        if next_v_str:
            try:
                next_v = datetime.fromisoformat(next_v_str.replace("Z", "+00:00"))
                if next_v > now + timedelta(minutes=5):
                    await db.table("topgg_vote_reminders").update({
                        "fallback_pending": False,
                        "fallback_shown_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                    }).eq("discord_user_id", user_id).execute()
                    return False
            except Exception:
                pass

        bot_id = interaction.client.user.id if interaction.client and interaction.client.user else None
        embed = build_pending_vote_notice_embed(bot_id)
        view = VoteReminderView(topgg_vote_url(runtime_bot_id=bot_id))

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        await db.table("topgg_vote_reminders").update({
            "fallback_pending": False,
            "fallback_shown_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }).eq("discord_user_id", user_id).execute()

        logger.info("Delivered ephemeral pending vote notice to user %s", user_id)
        return True
    except Exception:
        logger.debug("maybe_send_pending_vote_notice failed silently", exc_info=True)
        return False
