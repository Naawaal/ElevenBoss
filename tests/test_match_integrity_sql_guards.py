"""Source checks for US-42.4 migration 077."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "077_match_integrity_guards.sql"
VERIFY = ROOT / "supabase" / "scripts" / "verify_required_schema.sql"
RECOVERY = ROOT / "apps" / "discord_bot" / "core" / "match_recovery.py"


def test_migration_077_defines_abandon_and_reconcile():
    text = MIG.read_text(encoding="utf-8")
    assert "abandon_match_run" in text
    assert "reconcile_orphaned_match_locks" in text
    assert "release_match_lock" in text
    assert "FOR UPDATE" in text
    assert "status = 'abandoned'" in text
    assert "streaming" in text and "completing" in text


def test_verify_schema_lists_077_functions():
    text = VERIFY.read_text(encoding="utf-8")
    assert "function:abandon_match_run" in text
    assert "function:reconcile_orphaned_match_locks" in text


def test_recovery_uses_reconcile_not_blind_wipe():
    text = RECOVERY.read_text(encoding="utf-8")
    assert "reconcile_orphaned_match_locks" in text
    assert "classify_interrupted_run" in text
    assert '.delete().neq("discord_id", 0)' not in text
