import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

home_id = 999103001

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        # Clean
        cur.execute("DELETE FROM public.squad_assignments WHERE discord_id = %s", (home_id,))
        cur.execute("DELETE FROM public.squads WHERE discord_id = %s", (home_id,))
        cur.execute("DELETE FROM public.player_cards WHERE owner_id = %s", (home_id,))
        cur.execute("DELETE FROM public.players WHERE discord_id = %s", (home_id,))

        # Insert player
        cur.execute("INSERT INTO public.players (discord_id, username, club_name, manager_name, action_energy, global_lp, pvp_ranked_matches) VALUES (%s, %s, %s, %s, 100, 1200, 10)", (home_id, "user_999", "Club Alpha", "Mgr Alpha"))
        cur.execute("INSERT INTO public.squads (discord_id) VALUES (%s)", (home_id,))

        # Insert 11 cards
        positions = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD"]
        for idx, pos in enumerate(positions):
            cur.execute(
                """
                INSERT INTO public.player_cards (
                    owner_id, name, position, rarity, base_rating, potential, overall, pac, sho, pas, dri, "def", phy, fatigue, date_of_birth
                ) VALUES (%s, %s, %s, 'Rare', 80, 85, 80, 80, 80, 80, 80, 80, 80, 0, '2000-01-01'::DATE)
                RETURNING id
                """,
                (home_id, f"Player {idx+1}", pos),
            )
            card_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO public.squad_assignments (discord_id, player_card_id, position_slot)
                VALUES (%s, %s, %s)
                """,
                (home_id, card_id, idx + 1),
            )

        print("11 cards inserted into squad_assignments.")

        try:
            cur.execute("SELECT public.build_pvp_squad_snapshot(%s)", (home_id,))
            res = cur.fetchone()[0]
            print("build_pvp_squad_snapshot SUCCESS:", res)
        except Exception as e:
            print("build_pvp_squad_snapshot ERROR:", e)

    conn.commit()
