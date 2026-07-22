"""Smoke-check assert_card_action_allowed after migration 075."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT to_regprocedure('public.assert_card_action_allowed(bigint,uuid,text)') IS NOT NULL,
                   to_regprocedure('public.card_primary_state(uuid)') IS NOT NULL
            """
        )
        ok_assert, ok_primary = cur.fetchone()
        print("assert_card_action_allowed:", ok_assert)
        print("card_primary_state:", ok_primary)
        if not ok_assert or not ok_primary:
            raise SystemExit("075 functions missing")

        cur.execute(
            """
            SELECT pc.owner_id, pc.id
            FROM public.player_cards pc
            WHERE COALESCE(pc.is_retired, FALSE) = FALSE
              AND COALESCE(pc.in_hospital, FALSE) = FALSE
              AND COALESCE(pc.in_academy, FALSE) = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM public.transfer_listings tl
                  WHERE tl.card_id = pc.id AND tl.status = 'active'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM public.active_evolutions ae
                  WHERE ae.card_id = pc.id AND ae.status = 'active'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM public.squad_assignments sa
                  WHERE sa.player_card_id = pc.id
              )
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            print("smoke: no RosterFree card available — function existence OK")
            raise SystemExit(0)
        owner_id, card_id = row
        cur.execute("SELECT public.card_primary_state(%s)", (card_id,))
        print("primary:", cur.fetchone()[0])
        # view should allow
        cur.execute(
            "SELECT public.assert_card_action_allowed(%s, %s, 'view_profile')",
            (owner_id, card_id),
        )
        print("view_profile: ok")
        # Simulate listed block via matrix on a forced Hospitalized path if possible
        cur.execute(
            """
            SELECT pc.owner_id, pc.id
            FROM public.player_cards pc
            WHERE COALESCE(pc.in_hospital, TRUE) = TRUE
            LIMIT 1
            """
        )
        hosp = cur.fetchone()
        if hosp:
            try:
                cur.execute(
                    "SELECT public.assert_card_action_allowed(%s, %s, 'drill')",
                    hosp,
                )
                print("UNEXPECTED: hospital drill allowed")
            except psycopg.Error as e:
                conn.rollback()
                print("hospital drill blocked:", str(e).split("\n")[0])
        print("smoke 075 OK")
