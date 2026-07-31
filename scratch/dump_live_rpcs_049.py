"""Dump live RPC defs for 049 migration authoring."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
out = ROOT / "scratch" / "live_rpc_defs_049"
out.mkdir(exist_ok=True)

NAMES = (
    "process_match_result",
    "register_new_player",
    "claim_daily_pack",
    "allocate_skill_point",
    "process_stat_drill",
    "claim_evolution_reward",
    "train_with_fodder",
    "process_youth_intake",
    "sign_youth_scout_prospect",
    "process_daily_academy_growth",
    "transfer_mentor_xp",
    "evolution_stat_reward_steps",
)

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.oid::regprocedure::text
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = ANY(%s)
            ORDER BY 1
            """,
            (list(NAMES),),
        )
        procs = [r[0] for r in cur.fetchall()]
        print("found", len(procs))
        for p in procs:
            print(p)
            cur.execute("SELECT pg_get_functiondef(%s::regprocedure)", (p,))
            body = cur.fetchone()[0]
            safe = (
                p.replace("(", "_")
                .replace(")", "")
                .replace(",", "_")
                .replace(" ", "")
                .replace(".", "__")
            )
            (out / f"{safe}.sql").write_text(body, encoding="utf-8")
