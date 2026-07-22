"""Smoke-check abandon_match_run / reconcile_orphaned_match_locks after 077."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regprocedure('public.abandon_match_run(uuid,text)') IS NOT NULL"
        )
        assert cur.fetchone()[0], "abandon_match_run missing"
        cur.execute(
            "SELECT to_regprocedure('public.reconcile_orphaned_match_locks()') IS NOT NULL"
        )
        assert cur.fetchone()[0], "reconcile_orphaned_match_locks missing"
        cur.execute("SELECT public.reconcile_orphaned_match_locks()")
        deleted = cur.fetchone()[0]
        print("reconcile deleted:", deleted)
        # Idempotent no-op on random UUID
        cur.execute(
            "SELECT public.abandon_match_run(%s::uuid, %s)",
            ("00000000-0000-0000-0000-000000000001", "smoke"),
        )
        row = cur.fetchone()[0]
        print("abandon missing run:", row)
        assert row.get("ok") is False or row.get("reason") == "not_found"
    conn.commit()
print("smoke_match_integrity_077 OK")
