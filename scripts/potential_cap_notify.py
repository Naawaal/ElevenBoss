#!/usr/bin/env python3
"""
Print / send grouped manager DMs from potential_cap_repair_audit (049).

Default: print payloads only.
--send: Discord DMs + persist notified_at (or notification_error). Never rolls back repairs.
Reruns skip rows with notified_at already set.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RARITY_CAPS = {"Common": 75, "Rare": 85, "Epic": 92, "Legendary": 99}
DISCORD_DM_LIMIT = 1850  # leave room for optional "(part i/n)" prefix


def _chunk_message(body: str, limit: int = DISCORD_DM_LIMIT) -> list[str]:
    """Split a DM into Discord-safe chunks on blank lines / newlines."""
    if len(body) <= limit:
        return [body]
    parts: list[str] = []
    buf = ""
    for block in body.split("\n\n"):
        piece = block if not buf else buf + "\n\n" + block
        if len(piece) <= limit:
            buf = piece
            continue
        if buf:
            parts.append(buf)
            buf = ""
        if len(block) <= limit:
            buf = block
            continue
        # Hard-split oversized card block
        line_buf = ""
        for line in block.split("\n"):
            cand = line if not line_buf else line_buf + "\n" + line
            if len(cand) <= limit:
                line_buf = cand
            else:
                if line_buf:
                    parts.append(line_buf)
                line_buf = line[:limit]
                while len(line_buf) == limit and len(line) > limit:
                    parts.append(line_buf)
                    line = line[limit:]
                    line_buf = line[:limit]
                line_buf = line
        buf = line_buf
    if buf:
        parts.append(buf)
    return parts or [body[:limit]]


def _format_dm(rows: list[dict]) -> str:
    lines = [
        "**ElevenBoss — Player Potential Correction**",
        "",
        "We found and fixed a game-system issue where some player cards could show a "
        "potential higher than the maximum allowed for their rarity. This was our bug — "
        "not something you did wrong.",
        "",
        "Rarity absolute potential limits:",
        "• Common -> **75**",
        "• Rare -> **85**",
        "• Epic -> **92**",
        "• Legendary -> **99**",
        "",
        "Here is what changed for your club:",
        "",
    ]
    for r in rows:
        cap = RARITY_CAPS.get(str(r.get("rarity")), "?")
        lines.append(f"**{r.get('name') or r['card_id']} — {r['rarity']}** (max POT {cap})")
        lines.append(
            f"Before: OVR **{r['old_overall']}** · Potential **{r['old_potential']}**"
        )
        lines.append(
            f"After: OVR **{r['new_overall']}** · Potential **{r['new_potential']}**"
        )
        sp = int(r.get("refund_sp") or 0)
        coins = int(r.get("refund_coins") or 0)
        energy = int(r.get("refund_energy") or 0)
        if sp or coins or energy:
            bits = []
            if sp:
                bits.append(f"**{sp} Skill Point{'s' if sp != 1 else ''}**")
            if coins:
                bits.append(f"**{coins:,} Coins**")
            if energy:
                bits.append(f"**{energy} Action Energy**")
            lines.append(
                "Resources returned (for upgrades that had to be reversed to match the "
                f"corrected potential): {', '.join(bits)}"
            )
        else:
            lines.append(
                "Resources returned: **none required** — only the potential number was "
                "corrected; no paid upgrades were removed."
            )
        lines.append("")
    lines.extend(
        [
            "Your legitimate XP, match progress, and upgrades that stay within the "
            "corrected rarity limit were preserved.",
            "",
            "Potential caps are now enforced in both game logic and the database so this "
            "cannot happen again. Thanks for your patience while we keep progression fair.",
        ]
    )
    return "\n".join(lines)


async def _send_all(messages: dict[int, str], batch: str, dsn: str) -> None:
    import discord
    import psycopg

    token = os.environ.get("DISCORD_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN required for --send")

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        for owner_id, body in messages.items():
            try:
                user = await client.fetch_user(owner_id)
                chunks = _chunk_message(body)
                for i, chunk in enumerate(chunks):
                    prefix = f"(part {i + 1}/{len(chunks)})\n" if len(chunks) > 1 else ""
                    await user.send(prefix + chunk)
                with psycopg.connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE public.potential_cap_repair_audit
                            SET notified_at = NOW(),
                                notification_attempts = notification_attempts + 1,
                                notification_error = NULL
                            WHERE batch_id = %s AND owner_id = %s AND notified_at IS NULL
                            """,
                            (batch, owner_id),
                        )
                    conn.commit()
                print(f"sent {owner_id} parts={len(chunks)}")
            except Exception as exc:
                with psycopg.connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE public.potential_cap_repair_audit
                            SET notification_attempts = notification_attempts + 1,
                                notification_error = %s
                            WHERE batch_id = %s AND owner_id = %s AND notified_at IS NULL
                            """,
                            (str(exc)[:500], batch, owner_id),
                        )
                    conn.commit()
                print(f"fail {owner_id}: {exc}", file=sys.stderr)
        await client.close()

    await client.start(token)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    import psycopg
    from psycopg.rows import dict_row

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.*, c.name
                FROM public.potential_cap_repair_audit a
                LEFT JOIN public.player_cards c ON c.id = a.card_id
                WHERE a.batch_id = %s
                  AND a.repair_status IN ('repaired', 'refunded')
                  AND a.notified_at IS NULL
                ORDER BY a.owner_id, a.card_id
                """,
                (args.batch,),
            )
            rows = cur.fetchall()

    by_owner: dict[int, list] = defaultdict(list)
    for r in rows:
        if r.get("owner_id") is None:
            continue
        by_owner[int(r["owner_id"])].append(r)

    if not by_owner:
        print("No unrepaired/unnotified audit rows for this batch.")
        return 0

    messages = {oid: _format_dm(rs) for oid, rs in by_owner.items()}
    for oid, body in messages.items():
        print("=" * 40, oid)
        print(body)
        print()

    if args.send:
        asyncio.run(_send_all(messages, args.batch, dsn))
    else:
        print(f"(preview only — {len(messages)} managers; re-run with --send to deliver)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
