"""Live RPC smoke for P2P transfer market (list → buy → race fail → cancel).

Usage:
  python scratch/smoke_transfer_market.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")


def _json_flag(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        raw = value.strip().strip('"').lower()
        return "true" if raw == "true" else "false"
    return "false"


def main() -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value_json FROM public.game_config WHERE key = 'p2p_transfer_market_enabled'"
            )
            row = cur.fetchone()
            prior = _json_flag(row[0] if row else "false")

            cur.execute(
                """
                INSERT INTO public.game_config (key, value_json)
                VALUES ('p2p_transfer_market_enabled', 'true')
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            )
            conn.commit()

            cur.execute(
                """
                SELECT discord_id FROM public.players
                WHERE COALESCE(is_ai, FALSE) = FALSE
                ORDER BY discord_id LIMIT 2
                """
            )
            clubs = [r[0] for r in cur.fetchall()]
            if len(clubs) < 2:
                raise SystemExit("Need at least two human clubs")
            seller_id, buyer_id = clubs[0], clubs[1]

            cur.execute(
                """
                SELECT pc.id, pc.overall, pc.rarity, pc.potential, pc.date_of_birth
                FROM public.player_cards pc
                WHERE pc.owner_id = %s
                  AND COALESCE(pc.is_retired, FALSE) = FALSE
                  AND COALESCE(pc.in_academy, FALSE) = FALSE
                  AND pc.injury_tier IS NULL
                  AND COALESCE(pc.in_hospital, FALSE) = FALSE
                  AND NOT EXISTS (
                    SELECT 1 FROM public.squad_assignments sa WHERE sa.player_card_id = pc.id
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM public.transfer_listings tl
                    WHERE tl.card_id = pc.id AND tl.status = 'active'
                  )
                ORDER BY pc.overall DESC LIMIT 1
                """,
                (seller_id,),
            )
            card = cur.fetchone()
            if not card:
                raise SystemExit(f"No eligible card for seller {seller_id}")
            card_id = card[0]

            cur.execute(
                """
                SELECT public.compute_agent_offer(
                    %s, %s, public.card_age_from_dob(%s), %s
                )
                """,
                (card[1], card[2], card[4], card[3]),
            )
            fair = int(cur.fetchone()[0])
            price = max(50, int(fair * 0.9))
            print(f"seller={seller_id} buyer={buyer_id} card={card_id} fair={fair} price={price}")

            cur.execute(
                "SELECT public.create_transfer_listing(%s, %s, %s)",
                (seller_id, card_id, price),
            )
            created = cur.fetchone()[0]
            listing_id = created["listing_id"]
            print("listed:", listing_id)

            cur.execute(
                "UPDATE public.players SET coins = GREATEST(coins, %s) WHERE discord_id = %s",
                (price + 5_000, buyer_id),
            )
            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (buyer_id,))
            buyer_before = int(cur.fetchone()[0])
            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (seller_id,))
            seller_before = int(cur.fetchone()[0])
            conn.commit()

            cur.execute(
                "SELECT public.purchase_transfer_listing(%s, %s, %s)",
                (buyer_id, listing_id, price),
            )
            bought = cur.fetchone()[0]
            conn.commit()
            print("purchase #1 OK:", json.dumps(bought, default=str))

            # SAVEPOINT so a forced failure does not roll back the successful sale.
            cur.execute("SAVEPOINT race_try")
            race_failed = False
            try:
                cur.execute(
                    "SELECT public.purchase_transfer_listing(%s, %s, %s)",
                    (buyer_id, listing_id, price),
                )
                cur.fetchone()
            except Exception as exc:
                race_failed = True
                cur.execute("ROLLBACK TO SAVEPOINT race_try")
                print("purchase #2 rejected (expected):", str(exc).split("\n")[0][:180])
            if not race_failed:
                raise SystemExit("RACE FAIL: second purchase succeeded")

            cur.execute("SELECT owner_id FROM public.player_cards WHERE id = %s", (card_id,))
            if cur.fetchone()[0] != buyer_id:
                raise SystemExit("OWNER FAIL after purchase")

            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (buyer_id,))
            buyer_after = int(cur.fetchone()[0])
            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (seller_id,))
            seller_after = int(cur.fetchone()[0])
            tax = int(bought["tax_amount"])
            net = int(bought["seller_net"])
            if buyer_before - price != buyer_after:
                raise SystemExit(f"BUYER COINS FAIL {buyer_before} - {price} != {buyer_after}")
            if seller_before + net != seller_after:
                raise SystemExit(f"SELLER COINS FAIL {seller_before} + {net} != {seller_after}")
            if price != tax + net:
                raise SystemExit(f"TAX SPLIT FAIL {price} != {tax}+{net}")
            print(f"tax/net OK tax={tax} net={net}")

            # List + cancel on another eligible seller card if present.
            cur.execute(
                """
                SELECT pc.id FROM public.player_cards pc
                WHERE pc.owner_id = %s
                  AND COALESCE(pc.is_retired, FALSE) = FALSE
                  AND COALESCE(pc.in_academy, FALSE) = FALSE
                  AND pc.injury_tier IS NULL
                  AND COALESCE(pc.in_hospital, FALSE) = FALSE
                  AND NOT EXISTS (
                    SELECT 1 FROM public.squad_assignments sa WHERE sa.player_card_id = pc.id
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM public.transfer_listings tl
                    WHERE tl.card_id = pc.id AND tl.status = 'active'
                  )
                ORDER BY pc.overall DESC LIMIT 1
                """,
                (seller_id,),
            )
            other = cur.fetchone()
            if other:
                oid = other[0]
                cur.execute(
                    """
                    SELECT public.compute_agent_offer(
                        overall, rarity, public.card_age_from_dob(date_of_birth), potential
                    ) FROM public.player_cards WHERE id = %s
                    """,
                    (oid,),
                )
                p2 = max(50, int(cur.fetchone()[0]))
                cur.execute(
                    "SELECT public.create_transfer_listing(%s, %s, %s)",
                    (seller_id, oid, p2),
                )
                lid = cur.fetchone()[0]["listing_id"]
                cur.execute(
                    "SELECT public.cancel_transfer_listing(%s, %s)",
                    (seller_id, lid),
                )
                print("list+cancel OK:", cur.fetchone()[0]["status"])

            # Default off after smoke unless SMOKE_KEEP_FLAG=1 (staging).
            restore = prior if os.environ.get("SMOKE_KEEP_FLAG") == "1" else "false"
            cur.execute(
                """
                UPDATE public.game_config
                SET value_json = %s::jsonb
                WHERE key = 'p2p_transfer_market_enabled'
                """,
                (restore,),
            )
            conn.commit()
            print(f"SMOKE PASS — flag set to {restore}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SMOKE FAIL:", exc, file=sys.stderr)
        raise
