# tests/test_safe_defer.py
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.discord_bot.core.view_helpers import safe_defer


class TestSafeDefer(unittest.IsolatedAsyncioTestCase):
    async def test_already_done_returns_true(self) -> None:
        interaction = MagicMock()
        interaction.response.is_done.return_value = True

        ok = await safe_defer(interaction, ephemeral=True)
        self.assertTrue(ok)
        interaction.response.defer.assert_not_called()

    async def test_retries_after_429(self) -> None:
        interaction = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.user.id = 999
        rate_limited = discord.HTTPException(MagicMock(status=429), "slow down")
        rate_limited.retry_after = 0.01
        interaction.response.defer = AsyncMock(
            side_effect=[rate_limited, None],
        )

        with patch("apps.discord_bot.core.view_helpers.asyncio.sleep", new_callable=AsyncMock):
            ok = await safe_defer(interaction, ephemeral=True)

        self.assertTrue(ok)
        self.assertEqual(interaction.response.defer.await_count, 2)

    async def test_final_failure_sends_fallback(self) -> None:
        interaction = MagicMock()
        interaction.response.is_done.side_effect = [False, False]
        interaction.user.id = 111
        interaction.response.defer = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(status=429), "blocked"),
        )
        interaction.response.send_message = AsyncMock()

        with patch("apps.discord_bot.core.view_helpers.asyncio.sleep", new_callable=AsyncMock):
            ok = await safe_defer(interaction, ephemeral=True)

        self.assertFalse(ok)
        interaction.response.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
