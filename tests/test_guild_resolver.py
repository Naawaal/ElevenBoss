# tests/test_guild_resolver.py
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.discord_bot.core import guild_resolver
from apps.discord_bot.core.guild_resolver import (
    pause_season_if_guild_unreachable,
    resolve_bot_guild,
)


class TestResolveBotGuild(unittest.IsolatedAsyncioTestCase):
    async def test_cache_hit(self) -> None:
        bot = MagicMock()
        guild = MagicMock(spec=discord.Guild)
        bot.get_guild.return_value = guild

        resolved, unreachable = await resolve_bot_guild(bot, 123)
        self.assertIs(resolved, guild)
        self.assertFalse(unreachable)
        bot.fetch_guild.assert_not_called()

    async def test_fetch_not_found_is_unreachable(self) -> None:
        bot = MagicMock()
        bot.get_guild.return_value = None
        bot.fetch_guild = AsyncMock(side_effect=discord.NotFound(MagicMock(), "missing"))

        resolved, unreachable = await resolve_bot_guild(bot, 456)
        self.assertIsNone(resolved)
        self.assertTrue(unreachable)

    async def test_fetch_429_is_transient(self) -> None:
        bot = MagicMock()
        bot.get_guild.return_value = None
        bot.fetch_guild = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(status=429), "rate limited")
        )

        resolved, unreachable = await resolve_bot_guild(bot, 789)
        self.assertIsNone(resolved)
        self.assertFalse(unreachable)


class TestPauseSeasonIfGuildUnreachable(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        guild_resolver._logged_pause_attempts.clear()

    async def test_pauses_active_season(self) -> None:
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "season-1"}])
        )

        paused = await pause_season_if_guild_unreachable(
            db, "season-1", 101, "guild_unreachable"
        )
        self.assertTrue(paused)

    async def test_no_pause_when_already_completed(self) -> None:
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        paused = await pause_season_if_guild_unreachable(
            db, "season-2", 102, "guild_unreachable"
        )
        self.assertFalse(paused)


if __name__ == "__main__":
    unittest.main()
