# app/engine/team_strength.py

from dataclasses import dataclass
from app.engine.formation_rules import get_slot_rules
from app.engine.match_config import MatchEngineConfig

@dataclass
class TeamStrength:
    goalkeeper: float
    defense: float
    midfield: float
    attack: float
    overall: float

def calculate_team_strength(
    formation: str,
    players: list,
    is_home: bool = False,
    config: MatchEngineConfig | None = None,
    fitness_override: dict[str, float] | None = None,
) -> TeamStrength:
    """
    Calculate GK, Defense, Midfield, Attack, and Overall strengths for a starting XI.

    Args:
        formation: Name of the formation (e.g. '4-4-2').
        players: List of MatchPlayerInput objects or dicts, each with position, slot,
                 overall, and fitness fields.
        is_home: Whether the team is the home team (adds small home advantage).
        config: Configuration instance.
        fitness_override: Optional mapping of player_id -> current fitness (0.0–1.0).
                          When provided, overrides player.fitness to reflect mid-match
                          decay. Missing entries fall back to player.fitness / 100.

    Returns:
        TeamStrength object with calculated strengths.

    Notes:
        Missing slots (e.g. after a red card reduces the active XI below 11) are handled
        gracefully: the zone average simply uses whatever players remain. An empty zone
        falls back to overall_avg × 0.9.
    """
    if config is None:
        config = MatchEngineConfig()

    gk_ratings = []
    def_ratings = []
    mid_ratings = []
    att_ratings = []
    all_ratings = []

    for player in players:
        # Resolve fields (supports both dict and object)
        def get_val(attr, default=None):
            if isinstance(player, dict):
                return player.get(attr, default)
            return getattr(player, attr, default)

        slot = get_val("slot")
        pos = get_val("position")
        overall = get_val("overall", 50)
        player_id = get_val("player_id")

        # Mid-match fitness: prefer override dict, fall back to player.fitness field
        if fitness_override is not None and player_id and player_id in fitness_override:
            fitness_factor = max(config.min_fitness_factor, fitness_override[player_id])
        else:
            raw_fitness = get_val("fitness", 100)
            fitness_factor = max(config.min_fitness_factor * 100, raw_fitness) / 100.0

        # Position suitability factor
        is_gk_slot = (slot in config.gk_slots)
        is_gk_player = (pos == "GK")

        rules = get_slot_rules(slot)

        if is_gk_slot != is_gk_player:
            # Outfield player in goal, or goalkeeper playing outfield
            suitability_modifier = config.suitability_gk_swap
        elif pos in rules.get("natural", []):
            suitability_modifier = config.suitability_natural
        elif pos in rules.get("compatible", []):
            suitability_modifier = config.suitability_compatible
        else:
            suitability_modifier = config.suitability_out_of_position

        player_rating = overall * suitability_modifier * fitness_factor

        # Classify based on starting slot
        if slot in config.gk_slots:
            gk_ratings.append(player_rating)
        elif slot in config.defense_slots:
            def_ratings.append(player_rating)
        elif slot in config.midfield_slots:
            mid_ratings.append(player_rating)
        elif slot in config.attack_slots:
            att_ratings.append(player_rating)

        all_ratings.append(player_rating)

    # Calculate averages, handling fallbacks for empty sections (including sub-11 XIs)
    overall_avg = sum(all_ratings) / len(all_ratings) if all_ratings else 50.0
    gk_avg = sum(gk_ratings) / len(gk_ratings) if gk_ratings else overall_avg * 0.9
    def_avg = sum(def_ratings) / len(def_ratings) if def_ratings else overall_avg * 0.9
    mid_avg = sum(mid_ratings) / len(mid_ratings) if mid_ratings else overall_avg * 0.9
    att_avg = sum(att_ratings) / len(att_ratings) if att_ratings else overall_avg * 0.9

    # Home advantage: small bump to overall ratings if home
    home_mod = config.home_strength_boost if is_home else 1.0

    return TeamStrength(
        goalkeeper=round(gk_avg * home_mod, 2),
        defense=round(def_avg * home_mod, 2),
        midfield=round(mid_avg * home_mod, 2),
        attack=round(att_avg * home_mod, 2),
        overall=round(overall_avg * home_mod, 2)
    )


