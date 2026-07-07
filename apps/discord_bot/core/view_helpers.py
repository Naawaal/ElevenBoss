# apps/discord_bot/core/view_helpers.py
from __future__ import annotations

import discord


def set_view_controls_disabled(view: discord.ui.View, *, disabled: bool) -> None:
    for item in view.children:
        item.disabled = disabled


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
        await interaction.response.edit_message(embed=embed, view=view)
        return
    if interaction.message is not None:
        try:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
        except discord.NotFound:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return
    await interaction.edit_original_response(embed=embed, view=view)
