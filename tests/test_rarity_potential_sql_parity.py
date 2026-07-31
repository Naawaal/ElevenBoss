# tests/test_rarity_potential_sql_parity.py
from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from player_engine import RARITY_POT_CAPS

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


def test_python_sql_rarity_cap_parity() -> None:
    import psycopg

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for rarity, expected in RARITY_POT_CAPS.items():
                cur.execute("SELECT public.rarity_potential_cap(%s)", (rarity,))
                assert cur.fetchone()[0] == expected
            cur.execute("SELECT public.rarity_potential_cap(%s)", ("Mythic",))
            assert cur.fetchone()[0] is None
