"""Debug why prepare_manager_card_gifts returned empty."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "packages" / "gacha"), str(ROOT / "packages" / "player_engine")]
load_dotenv(ROOT / ".env")

from apps.discord_bot.core.card_payload import card_rpc_payload
from gacha import generate_manager_gift_epic, generate_manager_gift_legendary_mid

OWNER = 976054227459776582
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
gifts = [
    {"gift_slot": "epic", "card": card_rpc_payload(generate_manager_gift_epic(owner_id=OWNER))},
    {"gift_slot": "legendary_mid", "card": card_rpc_payload(generate_manager_gift_legendary_mid(owner_id=OWNER))},
]
print("payload slots", [g["gift_slot"] for g in gifts])
print("epic name", gifts[0]["card"]["name"], gifts[0]["card"]["overall"])

with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT campaign_id, gift_slot, claimed, pending_card IS NOT NULL AS prep "
        "FROM manager_card_gifts WHERE discord_id=%s",
        (OWNER,),
    )
    print("rows before", cur.fetchall())
    cur.execute("SELECT manager_card_gifts_enabled() AS e")
    print("enabled", cur.fetchone())
    try:
        cur.execute(
            "SELECT prepare_manager_card_gifts(%s, %s::jsonb) AS r",
            (OWNER, json.dumps(gifts)),
        )
        print("result", json.dumps(cur.fetchone()["r"], indent=2)[:1000])
    except Exception as e:
        print("ERROR", type(e), e)
        conn.rollback()
    cur.execute(
        "SELECT gift_slot, claimed, pending_card->>'name' AS name "
        "FROM manager_card_gifts WHERE discord_id=%s",
        (OWNER,),
    )
    print("rows after", cur.fetchall())
    conn.rollback()
