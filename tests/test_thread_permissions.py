# tests/test_thread_permissions.py
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.discord_bot.core.thread_permissions import restrict_thread_to_bot_and_reactions


class TestRestrictThread(unittest.IsolatedAsyncioTestCase):
    async def test_locks_thread(self) -> None:
        thread = MagicMock(spec=discord.Thread)
        thread.id = 1524325653246251061
        thread.edit = AsyncMock()
        guild = MagicMock(spec=discord.Guild)

        await restrict_thread_to_bot_and_reactions(thread, guild)

        thread.edit.assert_awaited_once_with(locked=True)

    async def test_swallows_http_exception(self) -> None:
        thread = MagicMock(spec=discord.Thread)
        thread.id = 1
        thread.edit = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(status=403), "forbidden"),
        )
        guild = MagicMock(spec=discord.Guild)

        await restrict_thread_to_bot_and_reactions(thread, guild)

        thread.edit.assert_awaited_once_with(locked=True)


if __name__ == "__main__":
    unittest.main()
