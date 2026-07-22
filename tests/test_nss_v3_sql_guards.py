# tests/test_nss_v3_sql_guards.py
"""Source checks for migration 083 match engine v3 events."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "083_match_engine_v3_events.sql"
VERIFY = ROOT / "supabase" / "scripts" / "verify_required_schema.sql"
RUNS = ROOT / "apps" / "discord_bot" / "core" / "match_runs.py"
STORE = ROOT / "apps" / "discord_bot" / "core" / "match_events_store.py"


def test_migration_083_defines_match_events_and_pins():
    text = MIG.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS public.match_events" in text
    assert "engine_version" in text
    assert "simulation_schema_version" in text
    assert "events_flushed_thru" in text
    assert "match_engine_v3_bot" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "match_events_select" in text
    assert "match_events_insert" in text


def test_verify_schema_lists_083_objects():
    text = VERIFY.read_text(encoding="utf-8")
    assert "table:public.match_events" in text
    assert "column:public.match_runs.engine_version" in text
    assert "column:public.match_runs.events_flushed_thru" in text
    assert "policy:public.match_events.match_events_select" in text


def test_match_runs_pins_on_create():
    text = RUNS.read_text(encoding="utf-8")
    assert "ENGINE_NSS_V3" in text
    assert "resolve_engine_version" in text
    assert "simulation_schema_version" in text


def test_events_store_exists():
    text = STORE.read_text(encoding="utf-8")
    assert "append_match_events" in text
    assert "events_flushed_thru" in text
