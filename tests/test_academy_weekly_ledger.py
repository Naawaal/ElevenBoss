# tests/test_academy_weekly_ledger.py
"""Academy weekly promote/sign counter helpers (pure mirrors for 051)."""
from __future__ import annotations


def _would_block(used: int, cap: int) -> bool:
    return int(used) >= int(cap)


def test_promote_cap_blocks_third() -> None:
    assert not _would_block(0, 2)
    assert not _would_block(1, 2)
    assert _would_block(2, 2)


def test_first_free_still_counts() -> None:
    """Fee may be 0 on first promote; counter still increments (spec assumption)."""
    promotes_used = 0
    fee = 0 if promotes_used == 0 else 500
    assert fee == 0
    promotes_used += 1
    assert promotes_used == 1
    fee2 = 0 if promotes_used == 0 else 500
    assert fee2 == 500


def test_paid_sign_independent_of_promote() -> None:
    promotes_used = 2
    paid_signings_used = 0
    assert _would_block(promotes_used, 2)
    assert not _would_block(paid_signings_used, 2)
