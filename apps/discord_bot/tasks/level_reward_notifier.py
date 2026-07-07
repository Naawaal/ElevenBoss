# apps/discord_bot/tasks/level_reward_notifier.py
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.views.level_reward_claim import ClaimAllLevelRewardsView

logger = logging.getLogger(__name__)


async def notify_pending_level_rewards(bot: commands.Bot) -> None:
    """DM club owners about unclaimed retroactive skill points (idempotent via notified flag)."""
    db = await get_client()
    pending_res = await (
        db.table("pending_level_rewards")
        .select("id, club_id, player_id, missing_points, player_cards!inner(owner_id, name, level)")
        .eq("claimed", False)
        .eq("notified", False)
        .execute()
    )
    rows = pending_res.data or []
    if not rows:
        logger.info("No pending level rewards to notify.")
        return

    by_owner: dict[int, list[dict]] = {}
    for row in rows:
        card = row.get("player_cards") or {}
        owner_id = int(card.get("owner_id") or row.get("club_id"))
        by_owner.setdefault(owner_id, []).append({**row, "_card": card})

    for owner_id, owner_rows in by_owner.items():
        try:
            user = await bot.fetch_user(owner_id)
            if user is None:
                continue

            lines: list[str] = []
            total_pts = 0
            for row in owner_rows:
                card = row.get("_card") or {}
                name = card.get("name", "Unknown")
                level = card.get("level", "?")
                pts = int(row["missing_points"])
                total_pts += pts
                lines.append(f"• **{name}** — Level {level} → **{pts}** skill points")

            embed = discord.Embed(
                title="🎁 Level-Up Rewards Available!",
                description=(
                    "Our new leveling system awards skill points for every player level-up. "
                    "Since your players leveled up before this update, you have unclaimed rewards!\n\n"
                    + "\n".join(lines[:20])
                    + (f"\n\n*…and {len(lines) - 20} more*" if len(lines) > 20 else "")
                ),
                color=0xFFD700,
            )
            embed.set_footer(text=f"Total unclaimed: {total_pts} skill points")
            embed.add_field(
                name="What's next?",
                value=(
                    "Click **Claim All** below, or open `/development` if DMs are disabled. "
                    "Then use **Allocate Skills** to spend points."
                ),
                inline=False,
            )

            view = ClaimAllLevelRewardsView()
            await user.send(embed=embed, view=view)

            row_ids = [r["id"] for r in owner_rows]
            await (
                db.table("pending_level_rewards")
                .update({"notified": True})
                .in_("id", row_ids)
                .execute()
            )
            logger.info("Sent level reward DM to owner %s (%s players).", owner_id, len(owner_rows))
        except discord.Forbidden:
            logger.warning(
                "DM blocked for owner %s — claim via /development hub (notified left false).",
                owner_id,
            )
        except Exception:
            logger.exception("Failed notifying owner %s about level rewards.", owner_id)
