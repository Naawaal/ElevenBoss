# apps/discord_bot/core/view_helpers.py
from __future__ import annotations

import discord


async def disable_view_on_timeout(view: discord.ui.View) -> None:
    for item in view.children:
        item.disabled = True
    try:
        if getattr(view, "message", None):
            await view.message.edit(view=view)
    except discord.HTTPException:
        pass
