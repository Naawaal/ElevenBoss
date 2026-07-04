# app/engine/lineup_validator.py

import uuid
from .formation_rules import SUPPORTED_FORMATIONS, get_slots_for_formation

def getattr_or_getitem(obj, attr, default=None):
    """
    Helper to access attributes of objects or keys of dictionaries.
    """
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)

def validate_lineup(
    formation: str,
    starters: dict[str, str | uuid.UUID],  # slot -> player_id
    bench: list[str | uuid.UUID],          # player_id list
    club_players: list                     # list of Player models/dicts
) -> tuple[bool, str]:
    """
    Validates a proposed lineup and bench.
    
    Returns:
        is_valid: bool
        error_message: str (empty if valid)
    """
    # 1. Formation support check
    if formation not in SUPPORTED_FORMATIONS:
        return False, f"Unsupported formation: {formation}."
        
    required_slots = get_slots_for_formation(formation)
    
    # 2. Exactly 11 starters check
    if len(starters) != 11:
        return False, f"Lineup must have exactly 11 starters (got {len(starters)})."
        
    # 3. Every required slot must be filled check
    for slot in required_slots:
        if slot not in starters or not starters[slot]:
            return False, f"Required slot '{slot}' is not filled."
            
    # Normalize IDs to strings for comparison
    club_player_map = {str(getattr_or_getitem(p, "id")): p for p in club_players}
    
    starter_ids = [str(pid) for pid in starters.values()]
    bench_ids = [str(pid) for pid in bench]
    all_selected_ids = starter_ids + bench_ids
    
    # 4. Club ownership check (all selected players must belong to the club)
    for pid in all_selected_ids:
        if pid not in club_player_map:
            return False, "Some selected players do not belong to your club."
            
    # 5. Duplicate players check
    if len(all_selected_ids) != len(set(all_selected_ids)):
        return False, "Duplicate players are not allowed in the lineup."
        
    # 6. Retired check
    for pid in all_selected_ids:
        player = club_player_map[pid]
        if getattr_or_getitem(player, "is_retired", False):
            name = getattr_or_getitem(player, "display_name")
            return False, f"Player {name} is retired and cannot be selected."
            
    # 7. Bench does not duplicate starters check
    for bid in bench_ids:
        if bid in starter_ids:
            return False, "A player cannot be on both the starters and the bench."
            
    return True, ""
