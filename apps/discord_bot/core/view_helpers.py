# apps/discord_bot/core/view_helpers.py
from __future__ import annotations

import asyncio
import logging

import discord

from apps.discord_bot.embeds.common_embeds import error_embed

logger = logging.getLogger(__name__)

_RATE_LIMIT_USER_MSG = (
    "Discord is temporarily rate-limiting requests. Please try again in a minute."
)


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True) -> bool:
    """Defer an interaction with 429 backoff; return False if ack could not be sent."""
    if interaction.response.is_done():
        return True

    for attempt in range(3):
        try:
            await interaction.response.defer(ephemeral=ephemeral)
            return True
        except discord.HTTPException as exc:
            if exc.status == 429 and attempt < 2:
                await asyncio.sleep(float(getattr(exc, "retry_after", 2) or 2))
                continue
            logger.warning(
                "defer failed for user %s (HTTP %s, attempt %s)",
                getattr(interaction.user, "id", "?"),
                exc.status,
                attempt + 1,
            )
            break

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                embed=error_embed(_RATE_LIMIT_USER_MSG),
                ephemeral=True,
            )
            return False
    except discord.HTTPException:
        logger.warning("Could not send rate-limit fallback to user %s", interaction.user.id)
    return False


def set_view_controls_disabled(view: discord.ui.View, *, disabled: bool) -> None:
    for item in view.children:
        item.disabled = disabled


def empty_state_line(subject: str, *, recovery: str = "Use Back or re-run the command.") -> str:
    """Consistent empty-list copy when a Select is omitted (Discord requires ≥1 option)."""
    return f"*{subject}*\n{recovery}"


def add_select_if_options(
    view: discord.ui.View,
    *,
    placeholder: str,
    options: list[discord.SelectOption],
    row: int,
    callback,
) -> discord.ui.Select | None:
    """Attach a Select only when ``options`` is non-empty. Returns the Select or None."""
    if not options:
        return None
    select = discord.ui.Select(placeholder=placeholder, options=options, row=row)
    select.callback = callback
    view.add_item(select)
    return select


async def disable_view_on_timeout(view: discord.ui.View) -> None:
    for item in view.children:
        item.disabled = True
    try:
        if getattr(view, "message", None):
            await view.message.edit(view=view)
    except discord.HTTPException:
        pass


async def edit_ephemeral_hub_message(
    interaction: discord.Interaction,
    embed: discord.Embed,
    view: discord.ui.View,
) -> None:
    """Edit ephemeral hub message after defer (shared by development + leaderboard hubs)."""
    if not interaction.response.is_done():
        try:
            await interaction.response.edit_message(embed=embed, view=view)
            return
        except discord.NotFound:
            logger.warning(
                "Hub edit_message failed (unknown interaction) for user %s — "
                "caller should defer before DB work",
                getattr(interaction.user, "id", "?"),
            )
            return
    if interaction.message is not None:
        try:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
        except discord.NotFound:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return
    await interaction.edit_original_response(embed=embed, view=view)
