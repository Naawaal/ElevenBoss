"""US-42.1 register idempotency contract checks."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "074_identity_ownership.sql"


def test_074_register_raises_already_registered_on_exists_and_unique():
    sql = MIG.read_text(encoding="utf-8")
    assert "ALREADY_REGISTERED" in sql
    assert "unique_violation" in sql
    assert "RAISE EXCEPTION 'ALREADY_REGISTERED'" in sql
    # Both pre-check and race handler
    assert sql.count("ALREADY_REGISTERED") >= 2


def test_074_register_rejects_whitespace_names():
    sql = MIG.read_text(encoding="utf-8")
    assert "Club name cannot be empty" in sql
    assert "Manager name cannot be empty" in sql
    assert "length(trim(p_club_name))" in sql


def test_074_register_sets_identity_active():
    sql = MIG.read_text(encoding="utf-8")
    assert "identity_status" in sql
    assert "'active'" in sql
    assert "last_qualifying_activity_at" in sql
