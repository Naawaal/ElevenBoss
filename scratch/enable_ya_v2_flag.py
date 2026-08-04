"""Enable youth_academy_v2_enabled after 095."""
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
            "UPDATE public.game_config SET value_json = 'true' "
            "WHERE key = 'youth_academy_v2_enabled'"
        )
        cur.execute(
            "SELECT COUNT(*) FROM public.player_cards "
            "WHERE in_academy AND pot_visible_lo IS NOT NULL"
        )
        n = cur.fetchone()[0]
        cur.execute(
            "SELECT value_json FROM public.game_config "
            "WHERE key = 'youth_academy_v2_enabled'"
        )
        flag = cur.fetchone()[0]
    conn.commit()
print(f"flag={flag} academy_with_ranges={n}")
