# scripts/migrate_ovr_fix.py
import asyncio
import os
import random
from dotenv import load_dotenv
from supabase import create_client, Client
from player_engine import calculate_true_ovr

load_dotenv()

_WEIGHTS = {
    "FWD": {"pac": 0.20, "sho": 0.35, "pas": 0.10, "dri": 0.20, "def": 0.05, "phy": 0.10},
    "MID": {"pac": 0.10, "sho": 0.15, "pas": 0.25, "dri": 0.20, "def": 0.15, "phy": 0.15},
    "DEF": {"pac": 0.15, "sho": 0.05, "pas": 0.10, "dri": 0.05, "def": 0.40, "phy": 0.25},
    "GK": {"pac": 0.15, "sho": 0.00, "pas": 0.15, "dri": 0.00, "def": 0.50, "phy": 0.20}
}

async def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_KEY")
        return

    # Use standard client for migrations/scripts
    db: Client = create_client(url, key)

    # 1. Fetch all player cards
    cards_res = db.table("player_cards").select("*").execute()
    cards = cards_res.data if cards_res else []
    if not cards:
        print("No player cards found to migrate.")
        return

    # 2. Fetch all playstyles
    ps_res = db.table("player_playstyles").select("*").execute()
    ps_data = ps_res.data if ps_res else []
    
    # Map card_id -> list of playstyles
    playstyles_map = {}
    for ps in ps_data:
        card_id = ps["card_id"]
        playstyles_map.setdefault(card_id, []).append(ps["playstyle_key"])

    print(f"Loaded {len(cards)} player cards and {len(ps_data)} playstyle records.")

    updated_count = 0
    for card in cards:
        card_id = card["id"]
        pos = card["position"]
        overall = card["overall"]
        potential = card.get("potential", 85)
        playstyles = playstyles_map.get(card_id, [])

        pac = card.get("pac", 50)
        sho = card.get("sho", 50)
        pas = card.get("pas", 50)
        dri = card.get("dri", 50)
        def_val = card.get("def", 50)
        phy = card.get("phy", 50)

        # Check if all 6 core attributes are exactly 50 (uninitialized bug state)
        is_flat_50 = (pac == 50 and sho == 50 and pas == 50 and dri == 50 and def_val == 50 and phy == 50)

        if is_flat_50:
            # Procedurally roll stats centered around their current overall
            weights = _WEIGHTS.get(pos, _WEIGHTS["MID"])
            stats = {}
            for attr, weight in weights.items():
                if weight >= 0.25:
                    stats[attr] = overall + random.randint(2, 12)
                elif weight >= 0.15:
                    stats[attr] = overall + random.randint(-5, 5)
                else:
                    stats[attr] = overall + random.randint(-20, -5)
                stats[attr] = max(10, min(99, stats[attr]))

            # Adjust to match the target OVR exactly
            new_ovr = calculate_true_ovr(pos, stats, playstyles, potential)
            diff = overall - new_ovr
            attempts = 0
            while diff != 0 and attempts < 10:
                shift = 1 if diff > 0 else -1
                for attr in stats:
                    if weights[attr] > 0:
                        stats[attr] = max(10, min(99, stats[attr] + shift))
                new_ovr = calculate_true_ovr(pos, stats, playstyles, potential)
                diff = overall - new_ovr
                attempts += 1

            # Update in database
            db.table("player_cards").update({
                "pac": stats["pac"],
                "sho": stats["sho"],
                "pas": stats["pas"],
                "dri": stats["dri"],
                "def": stats["def"],
                "phy": stats["phy"],
                "overall": new_ovr
            }).eq("id", card_id).execute()
            print(f"Generated stats for card {card['name']} ({pos}, {overall} OVR -> {new_ovr} OVR)")
            updated_count += 1
        else:
            # Just recalculate overall based on existing custom stats
            stats = {
                "pac": pac,
                "sho": sho,
                "pas": pas,
                "dri": dri,
                "def": def_val,
                "phy": phy
            }
            new_ovr = calculate_true_ovr(pos, stats, playstyles, potential)
            if new_ovr != overall:
                db.table("player_cards").update({
                    "overall": new_ovr
                }).eq("id", card_id).execute()
                print(f"Recalculated OVR for trained card {card['name']} ({pos}, {overall} OVR -> {new_ovr} OVR)")
                updated_count += 1

    print(f"Migration completed! Updated {updated_count} cards.")

if __name__ == "__main__":
    asyncio.run(main())
