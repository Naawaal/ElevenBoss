# apps/discord_bot/core/select_helpers.py
from __future__ import annotations

import discord


def rebuild_select_options(
    pool: list[dict],
    selected_id: str | None,
    *,
    value_key: str = "id",
    label_fn,
    description_fn=None,
    emoji_fn=None,
    max_options: int = 25,
) -> list[discord.SelectOption]:
    """Build select options with default=True on the current selection (Discord UI fix)."""
    options: list[discord.SelectOption] = []
    for item in pool[:max_options]:
        val = str(item[value_key])
        kw: dict = {
            "label": label_fn(item),
            "value": val,
            "default": bool(selected_id and val == str(selected_id)),
        }
        if description_fn:
            kw["description"] = description_fn(item)
        if emoji_fn:
            em = emoji_fn(item)
            if em:
                kw["emoji"] = em
        options.append(discord.SelectOption(**kw))
    return options
