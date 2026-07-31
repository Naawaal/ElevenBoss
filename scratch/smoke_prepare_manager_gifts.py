"""Smoke-prepare gifts for special manager; leave dm_status=pending for deploy notify."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "packages" / "gacha"),
    str(ROOT / "packages" / "player_engine"),
]
load_dotenv(ROOT / ".env")

from apps.discord_bot.core.card_payload import card_rpc_payload
from gacha import generate_manager_gift_epic, generate_manager_gift_legendary_mid

OWNER = 976054227459776582
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
gifts = [
    {
        "gift_slot": "epic",
        "card": card_rpc_payload(generate_manager_gift_epic(owner_id=OWNER)),
    },
    {
        "gift_slot": "legendary_mid",
        "card": card_rpc_payload(generate_manager_gift_legendary_mid(owner_id=OWNER)),
    },
]

with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT prepare_manager_card_gifts(%s, %s::jsonb) AS r",
        (OWNER, json.dumps(gifts)),
    )
    first = cur.fetchone()["r"]["gifts"]
    print("first prepare:")
    for g in first:
        c = g["card"]
        print(
            f"  {g['gift_slot']} already={g['already_prepared']} "
            f"{c['name']} {c['rarity']} {c['overall']} OVR"
        )

    cur.execute(
        "SELECT prepare_manager_card_gifts(%s, %s::jsonb) AS r",
        (OWNER, json.dumps(gifts)),
    )
    second = cur.fetchone()["r"]["gifts"]
    print("second prepare already flags:", [g["already_prepared"] for g in second])

    cur.execute(
        "UPDATE public.manager_card_gifts SET dm_status = 'pending' "
        "WHERE discord_id = %s AND claimed = FALSE",
        (OWNER,),
    )
    conn.commit()
    print("dm_status left pending for startup notifier")
