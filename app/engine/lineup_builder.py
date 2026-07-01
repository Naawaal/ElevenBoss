# app/engine/lineup_builder.py

from app.engine.formation_rules import get_slots_for_formation, get_slot_rules

def getattr_or_getitem(obj, attr, default=None):
    """
    Helper to access attributes of objects or keys of dictionaries.
    """
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)

def build_auto_lineup(players: list, formation: str) -> tuple[dict[str, any], list[any], list[str]]:
    """
    Auto-selects the best starting XI and bench players for a given formation.
    
    Args:
        players: List of Player model objects or dictionaries.
        formation: Name of the formation (e.g. '4-4-2').
        
    Returns:
        starters: Dict mapping slot -> Player.
        bench: List of Player objects not in starters.
        warnings: List of warning strings.
    """
    # 1. Filter out retired players
    active_players = [p for p in players if not getattr_or_getitem(p, "is_retired", False)]
    
    # 2. Get slots for the formation
    slots = get_slots_for_formation(formation)
    
    # 3. Greedy Matching
    # Calculate score for every possible (slot, player) combination
    candidates = []
    for slot in slots:
        rules = get_slot_rules(slot)
        for player in active_players:
            overall = getattr_or_getitem(player, "overall")
            fitness = getattr_or_getitem(player, "fitness", 100)
            pos = getattr_or_getitem(player, "position")
            
            # GK separation rules
            is_gk_slot = (slot == "GK")
            is_gk_player = (pos == "GK")
            
            if is_gk_slot != is_gk_player:
                position_bonus = -50  # Outfield in goal or GK outfield
            elif pos in rules.get("natural", []):
                position_bonus = 8
            elif pos in rules.get("compatible", []):
                position_bonus = 3
            else:
                position_bonus = -8
                
            score = overall + position_bonus + (fitness / 20.0)
            candidates.append((score, slot, player))
            
    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)
    
    starters = {}
    assigned_players = set()
    
    # Assign players to slots greedily
    for score, slot, player in candidates:
        if slot not in starters:
            player_id = getattr_or_getitem(player, "id")
            if player_id not in assigned_players:
                starters[slot] = player
                assigned_players.add(player_id)
                
    # 4. Generate warnings if a natural player is not selected for a slot
    warnings = []
    for slot in slots:
        if slot in starters:
            player = starters[slot]
            pos = getattr_or_getitem(player, "position")
            rules = get_slot_rules(slot)
            if pos not in rules.get("natural", []):
                name = getattr_or_getitem(player, "display_name")
                warnings.append(
                    f"Warning: No natural player available for slot {slot}. "
                    f"{name} ({pos}) selected instead."
                )
        else:
            warnings.append(f"Warning: Slot {slot} could not be filled.")
            
    # 5. Populate bench with remaining active players ordered by overall descending
    remaining_players = [
        p for p in active_players
        if getattr_or_getitem(p, "id") not in assigned_players
    ]
    remaining_players.sort(key=lambda p: getattr_or_getitem(p, "overall"), reverse=True)
    
    # Return top 7 remaining players on the bench (standard bench size)
    bench = remaining_players[:7]
    
    return starters, bench, warnings
