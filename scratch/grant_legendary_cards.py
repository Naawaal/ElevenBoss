"""Grant 2 Legendary MIDs and 2 Legendary DEFs to discord_id 976054227459776582."""
import os, uuid, json
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path('.').resolve() / '.env')
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

OWNER_ID = 976054227459776582

cards_to_add = [
    {
        "name": "Kevin De Bruyne",
        "position": "MID",
        "role": "Playmaker",
        "rarity": "Legendary",
        "base_rating": 90,
        "overall": 90,
        "potential": 99,
        "initial_potential": 99,
        "base_potential": 99,
        "age": 21,
        "pac": 82, "sho": 88, "pas": 95, "dri": 90, "def": 75, "phy": 82,
    },
    {
        "name": "Zinedine Zidane",
        "position": "MID",
        "role": "Box-to-Box",
        "rarity": "Legendary",
        "base_rating": 91,
        "overall": 91,
        "potential": 99,
        "initial_potential": 99,
        "base_potential": 99,
        "age": 22,
        "pac": 85, "sho": 87, "pas": 92, "dri": 94, "def": 80, "phy": 86,
    },
    {
        "name": "Virgil van Dijk",
        "position": "DEF",
        "role": "Ball-Playing Defender",
        "rarity": "Legendary",
        "base_rating": 90,
        "overall": 90,
        "potential": 99,
        "initial_potential": 99,
        "base_potential": 99,
        "age": 23,
        "pac": 84, "sho": 65, "pas": 82, "dri": 80, "def": 94, "phy": 92,
    },
    {
        "name": "Paolo Maldini",
        "position": "DEF",
        "role": "Stopper",
        "rarity": "Legendary",
        "base_rating": 91,
        "overall": 91,
        "potential": 99,
        "initial_potential": 99,
        "base_potential": 99,
        "age": 22,
        "pac": 86, "sho": 60, "pas": 78, "dri": 82, "def": 96, "phy": 90,
    },
]

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        now = datetime.now(timezone.utc)
        inserted_ids = []
        for c in cards_to_add:
            card_id = str(uuid.uuid4())
            dob = date(2026 - c["age"], 5, 15)
            contract_exp = now + timedelta(days=365)
            cur.execute("""
                INSERT INTO public.player_cards (
                    id, owner_id, name, position, role, rarity,
                    base_rating, level, overall, xp, morale, potential,
                    initial_potential, base_potential, age, date_of_birth,
                    contract_expires_at, pac, sho, pas, dri, def, phy,
                    skill_points, stat_xp, recent_match_ratings,
                    skill_points_earned, skill_points_spent, daily_alloc_count,
                    is_retired, fatigue, in_hospital, in_academy, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, 1, %s, 0, 100, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    0, %s, %s,
                    0, 0, 0,
                    false, 100, false, false, %s
                )
            """, (
                card_id, OWNER_ID, c["name"], c["position"], c["role"], c["rarity"],
                c["base_rating"], c["overall"], c["potential"],
                c["initial_potential"], c["base_potential"], c["age"], dob,
                contract_exp, c["pac"], c["sho"], c["pas"], c["dri"], c["def"], c["phy"],
                json.dumps({"pac": 0, "sho": 0, "pas": 0, "dri": 0, "def": 0, "phy": 0}),
                json.dumps([]), now
            ))
            inserted_ids.append((card_id, c["name"], c["position"], c["rarity"], c["overall"]))
        
        conn.commit()
        print("Successfully granted 4 Legendary cards to Discord ID", OWNER_ID)
        for cid, name, pos, rar, ovr in inserted_ids:
            print(f"  • [{pos}] {name} ({rar} {ovr} OVR) — Card ID: {cid}")
