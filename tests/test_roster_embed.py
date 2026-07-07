# tests/test_roster_embed.py
"""Full roster embed shows OVR per player."""
from __future__ import annotations

from apps.discord_bot.embeds.squad_embeds import roster_embed


def test_roster_embed_lists_ovr_per_player():
    cards = [
        {"id": "1", "name": "Striker One", "overall": 84, "position": "ST", "rarity": "Epic", "level": 3},
        {"id": "2", "name": "Keeper", "overall": 71, "position": "GK", "rarity": "Rare", "level": 1},
    ]
    embed = roster_embed(cards, current_page=0, total_pages=1, per_page=8)
    assert len(embed.fields) == 2
    assert "84 OVR" in embed.fields[0].name
    assert "Striker One" in embed.fields[0].value
    assert "71 OVR" in embed.fields[1].name
