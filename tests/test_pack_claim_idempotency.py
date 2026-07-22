# tests/test_pack_claim_idempotency.py
"""US-43 pack claim FR-006a contract + parser."""
from __future__ import annotations

from pathlib import Path

from apps.discord_bot.core.idempotent_outcome import parse_idempotent_outcome

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "082_pack_claim_idempotency.sql"


def test_migration_defines_idempotency_envelope() -> None:
    text = MIG.read_text(encoding="utf-8")
    assert "p_idempotency_key" in text
    assert "already_applied" in text
    assert "'status', 'applied'" in text or '"status", "applied"' in text or "status', 'applied'" in text
    assert "pack_claim_runs" in text
    assert "unique_violation" in text


def test_parse_pack_already_applied_payload() -> None:
    raw = {
        "status": "already_applied",
        "data": {"card_ids": ["a"], "claimed_at": "2026-07-22"},
    }
    out = parse_idempotent_outcome(raw)
    assert out.status == "already_applied"
    assert out.data["card_ids"] == ["a"]


def test_parse_pack_applied_payload() -> None:
    out = parse_idempotent_outcome({
        "status": "applied",
        "data": {"card_ids": ["b"]},
    })
    assert out.status == "applied"


def test_double_invoke_same_key_contract_in_sql() -> None:
    """Second insert collision must return already_applied, not RAISE to client."""
    text = MIG.read_text(encoding="utf-8")
    assert "WHEN unique_violation THEN" in text
    assert "already_applied" in text.split("unique_violation")[1][:400]
