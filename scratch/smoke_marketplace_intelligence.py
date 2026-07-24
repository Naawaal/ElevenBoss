"""SQL smoke for 086 marketplace intelligence RPCs."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT public.get_price_discovery(%s, %s, %s)", ("MID", "Rare", 78))
        discovery = cur.fetchone()[0]
        print("discovery sample_size=", discovery.get("sample_size"), "insufficient=", discovery.get("insufficient_data"))
        cur.execute(
            "SELECT public.get_market_analytics(NOW() - INTERVAL '7 days', NOW())"
        )
        analytics = cur.fetchone()[0]
        print("analytics keys=", sorted(analytics.keys()))
        assert "daily_volume" in analytics
        assert "tax_removed" in analytics
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='public' AND table_name='transfer_sales_log'
              AND column_name='fair_value_coins'
            """
        )
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT to_regclass('public.card_ownership_history')")
        assert cur.fetchone()[0] is not None
print("smoke_marketplace_intelligence OK")
print(json.dumps({"discovery_keys": sorted(discovery.keys())}, indent=2))
