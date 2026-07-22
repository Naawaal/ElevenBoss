# tests/test_hub_hot_path_wave3.py
"""US-45 marketplace + leaderboard hot-path contracts."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_marketplace_hub_and_sell_gather() -> None:
    cog = (ROOT / "apps/discord_bot/cogs/marketplace_cog.py").read_text(encoding="utf-8")
    assert "asyncio.gather" in cog
    assert "hub_timer(\"marketplace\")" in cog or "hub_timer('marketplace')" in cog
    views = (ROOT / "apps/discord_bot/views/marketplace_transfer.py").read_text(encoding="utf-8")
    assert "asyncio.gather" in views


def test_leaderboard_defer_timer_division_cache() -> None:
    text = (ROOT / "apps/discord_bot/cogs/leaderboard_cog.py").read_text(encoding="utf-8")
    assert "interaction.response.defer" in text
    assert "hub_timer(\"leaderboard\")" in text or "hub_timer('leaderboard')" in text
    assert "load_global_divisions" in text
    assert "asyncio.gather" in text
