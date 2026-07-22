"""Gate-message smoke checks for evolution hub pre-checks."""
from __future__ import annotations

from apps.discord_bot.cogs.development_cog import evolution_start_gate_message


def test_gate_allows_when_can_start() -> None:
    assert evolution_start_gate_message({"active_count": 1, "can_start": True}) is None


def test_gate_blocks_full_slots() -> None:
    msg = evolution_start_gate_message({"active_count": 3, "max_active": 3, "can_start": False})
    assert msg is not None
    assert "3 evolutions" in msg


def test_gate_blocks_legacy_overflow() -> None:
    msg = evolution_start_gate_message({"active_count": 7, "max_active": 3, "can_start": False})
    assert msg is not None
    assert "7" in msg
    assert "3" in msg


def test_gate_respects_config_max_active() -> None:
    assert evolution_start_gate_message({"active_count": 3, "max_active": 4, "can_start": True}) is None
    msg = evolution_start_gate_message({"active_count": 4, "max_active": 4, "can_start": False})
    assert msg is not None
    assert "4 evolutions" in msg


def test_gate_blocks_cooldown() -> None:
    msg = evolution_start_gate_message({
        "active_count": 1,
        "can_start": False,
        "cooldown_remaining_seconds": 27120,
    })
    assert msg is not None
    assert "7h 32m" in msg
