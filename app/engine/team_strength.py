# app/engine/team_strength.py

from dataclasses import dataclass
from app.engine.formation_rules import get_slot_rules

@dataclass
class TeamStrength:
    goalkeeper: float
    defense: float
    midfield: float
    attack: float
    overall: float

def calculate_team_strength(formation: str, players: list, is_home: bool = False) -> TeamStrength:
    """
    Calculate GK, Defense, Midfield, Attack, and Overall strengths for a starting XI.
    
    Args:
        formation: Name of the formation (e.g. '4-4-2').
        players: List of dicts or Player objects, each must have position, slot, overall, fitness.
        is_home: Whether the team is the home team (adds small home advantage).
        
    Returns:
        TeamStrength object with calculated strengths.
    """
    gk_ratings = []
    def_ratings = []
    mid_ratings = []
    att_ratings = []
    all_ratings = []
    
    # Slot groups
    GK_SLOTS = {"GK"}
    DEFENSE_SLOTS = {"LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB"}
    MIDFIELD_SLOTS = {"LM", "CM1", "CM2", "CM3", "RM", "LDM", "RDM", "CAM"}
    ATTACK_SLOTS = {"LW", "ST", "RW", "ST1", "ST2"}
    
    for player in players:
        # Resolve fields (supports both dict and object)
        def get_val(attr, default=None):
            if isinstance(player, dict):
                return player.get(attr, default)
            return getattr(player, attr, default)
            
        slot = get_val("slot")
        pos = get_val("position")
        overall = get_val("overall", 50)
        fitness = get_val("fitness", 100)
        
        # Position suitability factor
        is_gk_slot = (slot == "GK")
        is_gk_player = (pos == "GK")
        
        rules = get_slot_rules(slot)
        
        if is_gk_slot != is_gk_player:
            # Outfield player in goal, or goalkeeper playing outfield
            suitability_modifier = 0.2
        elif pos in rules.get("natural", []):
            suitability_modifier = 1.0
        elif pos in rules.get("compatible", []):
            suitability_modifier = 0.85
        else:
            suitability_modifier = 0.6
            
        # Suitable rating incorporating fitness
        fitness_factor = max(10, fitness) / 100.0
        player_rating = overall * suitability_modifier * fitness_factor
        
        # Classify based on starting slot
        if slot in GK_SLOTS:
            gk_ratings.append(player_rating)
        elif slot in DEFENSE_SLOTS:
            def_ratings.append(player_rating)
        elif slot in MIDFIELD_SLOTS:
            mid_ratings.append(player_rating)
        elif slot in ATTACK_SLOTS:
            att_ratings.append(player_rating)
            
        all_ratings.append(player_rating)
        
    # Calculate averages, handling fallbacks for empty sections
    overall_avg = sum(all_ratings) / len(all_ratings) if all_ratings else 50.0
    gk_avg = sum(gk_ratings) / len(gk_ratings) if gk_ratings else overall_avg * 0.9
    def_avg = sum(def_ratings) / len(def_ratings) if def_ratings else overall_avg * 0.9
    mid_avg = sum(mid_ratings) / len(mid_ratings) if mid_ratings else overall_avg * 0.9
    att_avg = sum(att_ratings) / len(att_ratings) if att_ratings else overall_avg * 0.9
    
    # Home advantage: small 5% bump to all ratings if home
    home_mod = 1.05 if is_home else 1.0
    
    return TeamStrength(
        goalkeeper=round(gk_avg * home_mod, 2),
        defense=round(def_avg * home_mod, 2),
        midfield=round(mid_avg * home_mod, 2),
        attack=round(att_avg * home_mod, 2),
        overall=round(overall_avg * home_mod, 2)
    )
