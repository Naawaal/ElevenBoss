# tests/test_lifecycle_idempotency.py
"""Exactly-once operation key semantics (pure)."""
from __future__ import annotations

from leagues.operation_keys import fixture_settle, season_prepare


def test_operation_keys_stable():
    assert season_prepare("abc") == "season:abc:prepare"
    assert fixture_settle("f1") == "fixture:f1:settle"


def test_fake_store_100x_acquire_once():
    """Simulate 100 retries: only first acquire wins per key."""
    store: set[str] = set()

    def acquire(key: str) -> bool:
        if key in store:
            return False
        store.add(key)
        return True

    key = season_prepare("season-1")
    wins = sum(1 for _ in range(100) if acquire(key))
    assert wins == 1
    assert key in store

    fkey = fixture_settle("fix-9")
    wins_f = sum(1 for _ in range(100) if acquire(fkey))
    assert wins_f == 1
