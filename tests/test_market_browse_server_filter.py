"""Guard: Transfer Board must not regress to fetch-N / filter-in-Python."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_limit_50_active_listings_in_board_path() -> None:
    src = (
        ROOT / "apps/discord_bot/views/marketplace_transfer.py"
    ).read_text(encoding="utf-8")
    # Production browse path must call the RPC; legacy comment may remain.
    assert "browse_transfer_market" in src
    assert 'eq("status", "active").gt("expires_at"' not in src
