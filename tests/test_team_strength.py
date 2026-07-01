# tests/test_team_strength.py

import unittest
from app.engine.team_strength import calculate_team_strength
from app.engine.match_config import MatchEngineConfig
from app.engine.match_engine import MatchPlayerInput

def create_player(player_id: str, slot: str, position: str, overall: int, fitness: int = 100) -> MatchPlayerInput:
    return MatchPlayerInput(
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        slot=slot,
        overall=overall,
        potential=overall + 5,
        fitness=fitness,
        morale=80
    )

def create_standard_xi(prefix: str, overall: int, fitness: int = 100) -> list[MatchPlayerInput]:
    return [
        create_player(f"{prefix}_gk", "GK", "GK", overall, fitness),
        create_player(f"{prefix}_lb", "LB", "LB", overall, fitness),
        create_player(f"{prefix}_cb1", "CB1", "CB", overall, fitness),
        create_player(f"{prefix}_cb2", "CB2", "CB", overall, fitness),
        create_player(f"{prefix}_rb", "RB", "RB", overall, fitness),
        create_player(f"{prefix}_lm", "LM", "LM", overall, fitness),
        create_player(f"{prefix}_cm1", "CM1", "CM", overall, fitness),
        create_player(f"{prefix}_cm2", "CM2", "CM", overall, fitness),
        create_player(f"{prefix}_rm", "RM", "RM", overall, fitness),
        create_player(f"{prefix}_st1", "ST1", "ST", overall, fitness),
        create_player(f"{prefix}_st2", "ST2", "ST", overall, fitness),
    ]

class TestTeamStrength(unittest.TestCase):
    def setUp(self):
        self.players = create_standard_xi("h", 80)

    def test_standard_strength_calculation(self):
        strength = calculate_team_strength("4-4-2", self.players, is_home=False)
        self.assertGreater(strength.goalkeeper, 70)
        self.assertGreater(strength.defense, 70)
        self.assertGreater(strength.midfield, 70)
        self.assertGreater(strength.attack, 70)
        self.assertGreater(strength.overall, 70)

    def test_out_of_position_penalty(self):
        # Swap ST with GK
        bad_players = self.players.copy()
        gk_idx = next(i for i, p in enumerate(bad_players) if p.slot == "GK")
        st_idx = next(i for i, p in enumerate(bad_players) if p.slot == "ST1")
        
        p_gk = bad_players[gk_idx]
        p_st = bad_players[st_idx]
        
        bad_players[gk_idx] = create_player(p_gk.player_id, "ST1", p_gk.position, p_gk.overall)
        bad_players[st_idx] = create_player(p_st.player_id, "GK", p_st.position, p_st.overall)
        
        strength = calculate_team_strength("4-4-2", bad_players, is_home=False)
        # GK strength should drop heavily due to outfield player in goal
        self.assertLess(strength.goalkeeper, 30)

    def test_fitness_modifier_boundaries(self):
        # Extremely low fitness (e.g. 5) should be bounded by min_fitness_factor (default 0.1, i.e., 10%)
        very_fatigued = create_standard_xi("h", 80, fitness=5)
        strength = calculate_team_strength("4-4-2", very_fatigued, is_home=False)
        
        # Expected rating overall should be around 80 * 0.1 = 8
        self.assertLess(strength.overall, 10.0)
        self.assertGreater(strength.overall, 5.0)

    def test_home_advantage_multiplier(self):
        config = MatchEngineConfig(home_strength_boost=1.10)
        strength_away = calculate_team_strength("4-4-2", self.players, is_home=False, config=config)
        strength_home = calculate_team_strength("4-4-2", self.players, is_home=True, config=config)
        
        self.assertAlmostEqual(strength_home.overall, strength_away.overall * 1.10, places=1)
