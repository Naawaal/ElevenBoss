"""Helpers/tests for contract renew hotfix (047-fix-contract-renew)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.discord_bot.core.contract_renew import make_renew_idempotency_key
from economy.wages import contract_blocks_xi
from player_engine import can_renew_contract


def renew_ui_success_ok(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
    grace_days: int = 7,
) -> bool:
    """True when profile UI may claim a successful renew (not past grace)."""
    return not contract_blocks_xi(expires_at, now, grace_days=grace_days)


def test_make_renew_key_is_not_permanent_card_only() -> None:
    card = "854ec9e5-b09a-4941-8341-7c9cc0d2bb7c"
    key = make_renew_idempotency_key(card)
    assert key.startswith(f"contract_renewal:{card}:")
    assert key != f"contract_renewal:{card}"
    assert make_renew_idempotency_key(card) != key


def test_renew_ui_rejects_past_grace_as_success() -> None:
    now = datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc)
    expired = now - timedelta(days=10)
    assert renew_ui_success_ok(expired, now=now, grace_days=7) is False
    future = now + timedelta(days=7)
    assert renew_ui_success_ok(future, now=now, grace_days=7) is True


def test_age_gate_unchanged() -> None:
    assert can_renew_contract(34) is True
    assert can_renew_contract(35) is False
