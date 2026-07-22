# tests/test_idempotent_outcome.py
"""US-43 FR-006a idempotent outcome parser."""
from __future__ import annotations

from apps.discord_bot.core.idempotent_outcome import parse_idempotent_outcome


def test_applied_explicit() -> None:
    out = parse_idempotent_outcome({"status": "applied", "data": {"coins": 10}})
    assert out.status == "applied"
    assert out.data["coins"] == 10


def test_already_applied_explicit() -> None:
    out = parse_idempotent_outcome({"status": "already_applied", "data": {"coins": 10}})
    assert out.status == "already_applied"


def test_legacy_replay_maps_to_already_applied() -> None:
    out = parse_idempotent_outcome({"replay": True, "coins": 50, "energy": 10})
    assert out.status == "already_applied"
    assert out.data["coins"] == 50


def test_legacy_already_applied_flag() -> None:
    out = parse_idempotent_outcome({"already_applied": True, "ok": True})
    assert out.status == "already_applied"


def test_rejected() -> None:
    out = parse_idempotent_outcome({"ok": False, "reason": "insufficient_coins"})
    assert out.status == "rejected"
    assert out.reason == "insufficient_coins"


def test_default_success_is_applied() -> None:
    out = parse_idempotent_outcome({"replay": False, "coins": 1})
    assert out.status == "applied"
    assert out.data["coins"] == 1
