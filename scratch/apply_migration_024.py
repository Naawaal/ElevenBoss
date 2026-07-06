"""Apply migration 024_enforce_pot_stat_caps.sql via DATABASE_URL."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

_DEBUG_LOG = "debug-4aa967.log"
_MIGRATION = "supabase/migrations/024_enforce_pot_stat_caps.sql"


def _log(message: str, data: dict, hypothesis_id: str = "M") -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "4aa967",
                        "runId": "migration-024",
                        "hypothesisId": hypothesis_id,
                        "timestamp": int(time.time() * 1000),
                        "location": "scratch/apply_migration_024.py",
                        "message": message,
                        "data": data,
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    # #endregion


async def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found", file=sys.stderr)
        _log("missing DATABASE_URL", {})
        return 1

    if not os.path.exists(_MIGRATION):
        print(f"Missing {_MIGRATION}", file=sys.stderr)
        return 1

    sql = open(_MIGRATION, encoding="utf-8").read()
    # asyncpg: one statement per execute (split on function/grant boundaries)
    statements = [s.strip() for s in sql.split("$$ LANGUAGE plpgsql;") if s.strip()]
    chunks: list[str] = []
    for i, part in enumerate(statements):
        if i < len(statements) - 1:
            chunks.append(part.strip() + "$$ LANGUAGE plpgsql;")
        else:
            for grant in part.split(";"):
                grant = grant.strip()
                if grant and not grant.startswith("--"):
                    chunks.append(grant + ";")

    engine = create_async_engine(database_url)

    async with engine.begin() as conn:
        _log("executing migration", {"file": _MIGRATION, "chunks": len(chunks)})
        print(f"Executing {_MIGRATION} ({len(chunks)} statements)...")
        for idx, stmt in enumerate(chunks, 1):
            await conn.execute(text(stmt))
            _log("statement ok", {"index": idx})

        drill_row = (
            await conn.execute(
                text(
                    """
                    SELECT
                        strpos(prosrc, 'Player is already at maximum overall for their potential') > 0
                            AS pot_gate,
                        strpos(prosrc, 'Stat is already at maximum') > 0 AS stat_gate
                    FROM pg_proc
                    WHERE proname = 'process_stat_drill'
                    ORDER BY oid DESC
                    LIMIT 1
                    """
                )
            )
        ).mappings().first()

        evo_row = (
            await conn.execute(
                text(
                    """
                    SELECT strpos(prosrc, 'blocked_by_cap') > 0 AS evo_cap_gate
                    FROM pg_proc
                    WHERE proname = 'claim_evolution_reward'
                    ORDER BY oid DESC
                    LIMIT 1
                    """
                )
            )
        ).mappings().first()

        verify = {
            "process_stat_drill": dict(drill_row) if drill_row else None,
            "claim_evolution_reward": dict(evo_row) if evo_row else None,
        }
        _log("verification", verify)

        if not drill_row or not drill_row["pot_gate"] or not drill_row["stat_gate"]:
            print("Verification FAILED: process_stat_drill gates missing", file=sys.stderr)
            print(verify, file=sys.stderr)
            return 1
        if not evo_row or not evo_row["evo_cap_gate"]:
            print("Verification FAILED: claim_evolution_reward cap gate missing", file=sys.stderr)
            print(verify, file=sys.stderr)
            return 1

        print("Verification OK:", verify)

    await engine.dispose()
    print("Migration 024 applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
