"""US-42.1 guild remove must not delete clubs."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "discord_bot" / "main.py"
RESOLVER = ROOT / "apps" / "discord_bot" / "core" / "guild_resolver.py"


def test_on_guild_remove_uses_pause_not_delete():
    main = MAIN.read_text(encoding="utf-8")
    assert "on_guild_remove" in main
    assert "pause_seasons_for_guild" in main
    # Within on_guild_remove body, no players delete
    start = main.index("async def on_guild_remove")
    end = main.index("\ndef main", start)
    body = main[start:end]
    assert "pause_seasons_for_guild" in body
    assert '.table("players").delete' not in body
    assert "DELETE FROM players" not in body
    assert "US-42.1" in body


def test_pause_seasons_for_guild_does_not_delete_players():
    src = RESOLVER.read_text(encoding="utf-8")
    assert "async def pause_seasons_for_guild" in src
    start = src.index("async def pause_seasons_for_guild")
    # Function ends at next top-level async def or end
    rest = src[start:]
    next_def = rest.find("\nasync def ", 1)
    body = rest if next_def < 0 else rest[:next_def]
    assert '.table("players").delete' not in body
    assert "DELETE FROM players" not in body
    assert "US-42.1" in body
