# tests/test_league_play_xi_gate.py
"""League Play: a blocked opponent must be reported, never a silent no-match."""
from __future__ import annotations

import asyncio

from apps.discord_bot.cogs.battle_cog import _dm_xi_block
from apps.discord_bot.core.squad_validity import opponent_xi_block_message


class _FakeUser:
    def __init__(self) -> None:
        self.embeds: list = []

    async def send(self, *, embed):
        self.embeds.append(embed)


class _FakeBot:
    def __init__(self) -> None:
        self.user = _FakeUser()

    async def fetch_user(self, _id: int):
        return self.user


def _sent_text(bot: _FakeBot) -> str:
    assert bot.user.embeds, "manager was not told why the match did not start"
    return bot.user.embeds[-1].description or ""


def test_opponent_block_names_club_and_is_not_self_copy():
    msg = opponent_xi_block_message("Crimson FC")
    assert "Crimson FC" in msg
    assert "Your starting" not in msg


def test_dm_goes_to_active_manager_when_opponent_is_blocked():
    bot = _FakeBot()
    asyncio.run(_dm_xi_block(bot, db=None, active_player_id=111, blocked_id=222, blocked_club="Crimson FC"))
    assert "Crimson FC" in _sent_text(bot)


def test_dm_uses_own_block_reason_when_active_manager_is_blocked():
    class _DB:
        pass

    async def _run():
        import apps.discord_bot.core.squad_validity as sv

        original = sv.club_xi_block_reason

        async def _fake_reason(*_args, **_kwargs):
            return "Your starting XI is invalid."

        # battle_cog imported the symbol directly
        import apps.discord_bot.cogs.battle_cog as bc

        bc.club_xi_block_reason = _fake_reason
        try:
            bot = _FakeBot()
            await _dm_xi_block(bot, db=_DB(), active_player_id=111, blocked_id=111, blocked_club="My FC")
            return _sent_text(bot)
        finally:
            bc.club_xi_block_reason = original

    assert "Your starting XI is invalid." in asyncio.run(_run())


def test_no_dm_without_an_active_manager():
    bot = _FakeBot()
    asyncio.run(_dm_xi_block(bot, db=None, active_player_id=None, blocked_id=222, blocked_club="Crimson FC"))
    assert not bot.user.embeds
