# apps/discord_bot/core/contract_renew.py
"""Contract renew helpers (047-fix-contract-renew)."""
from __future__ import annotations

from uuid import uuid4


def make_renew_idempotency_key(card_id: str) -> str:
    """Per-click economy idempotency key — never permanent contract_renewal:{card_id} alone."""
    return f"contract_renewal:{card_id}:{uuid4()}"
