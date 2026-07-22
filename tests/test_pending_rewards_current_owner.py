"""US-42.1 pending rewards must credit current card owner."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"


def _latest_claim_sql() -> str:
    # Prefer newest migration that defines the function
    hits: list[Path] = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        if "CREATE OR REPLACE FUNCTION public.claim_pending_level_rewards" in text:
            hits.append(path)
    assert hits, "claim_pending_level_rewards not found in migrations"
    return hits[-1].read_text(encoding="utf-8")


def test_claim_pending_filters_current_owner_id():
    sql = _latest_claim_sql()
    assert "c.owner_id = p_owner_id" in sql
    assert "WHERE id = v_row.player_id AND owner_id = p_owner_id" in sql


def test_claim_pending_does_not_pay_on_stale_club_id_alone():
    sql = _latest_claim_sql()
    # Must join cards and filter owner_id — not WHERE pr.club_id = p_owner_id alone
    assert "JOIN public.player_cards" in sql or "JOIN public.player_cards c" in sql
    assert "AND c.owner_id = p_owner_id" in sql
    # Stale-only pattern should not be the sole filter
    assert "WHERE NOT pr.claimed\n          AND pr.club_id = p_owner_id" not in sql
