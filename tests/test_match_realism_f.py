# tests/test_match_realism_f.py

import unittest
import random
from app.engine.match_engine import (
    MatchPlayerInput,
    MatchTeamInput,
    MatchSimulationInput,
    simulate_match,
)
from app.engine.match_rating import calculate_player_ratings
from app.engine.match_config import MatchEngineConfig
from app.engine.match_event_generator import attribute_goal

def create_player(player_id: str, slot: str, position: str, overall: int, consistency: int = 70) -> MatchPlayerInput:
    return MatchPlayerInput(
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        slot=slot,
        overall=overall,
        potential=overall + 5,
        fitness=100,
        morale=80,
        consistency=consistency,
    )

def create_standard_xi(prefix: str, overall: int, consistency: int = 70) -> list[MatchPlayerInput]:
    return [
        create_player(f"{prefix}_gk", "GK", "GK", overall, consistency),
        create_player(f"{prefix}_lb", "LB", "LB", overall, consistency),
        create_player(f"{prefix}_cb1", "CB1", "CB", overall, consistency),
        create_player(f"{prefix}_cb2", "CB2", "CB", overall, consistency),
        create_player(f"{prefix}_rb", "RB", "RB", overall, consistency),
        create_player(f"{prefix}_lm", "LM", "LM", overall, consistency),
        create_player(f"{prefix}_cm1", "CM1", "CM", overall, consistency),
        create_player(f"{prefix}_cm2", "CM2", "CM", overall, consistency),
        create_player(f"{prefix}_rm", "RM", "RM", overall, consistency),
        create_player(f"{prefix}_st1", "ST1", "ST", overall, consistency),
        create_player(f"{prefix}_st2", "ST2", "ST", overall, consistency),
    ]

class TestMatchRealismF(unittest.TestCase):

    def setUp(self):
        self.home_players = create_standard_xi("h", 80)
        self.away_players = create_standard_xi("a", 70)
        
        self.home_team = MatchTeamInput(
            club_id="club_home",
            club_name="Home FC",
            formation="4-4-2",
            players=self.home_players,
            is_home=True
        )
        self.away_team = MatchTeamInput(
            club_id="club_away",
            club_name="Away FC",
            formation="4-4-2",
            players=self.away_players,
            is_home=False
        )

    def test_consistency_rating_ranges(self):
        """Verify base rating roll range adapts dynamically to player consistency."""
        config = MatchEngineConfig()
        rng = random.Random(42)

        # 1. Low consistency player (consistency = 40) should have base rating range [4.5, 8.5]
        # (width of 4.0)
        p_low = [create_player("low", "ST1", "ST", 80, consistency=40)]
        team_low = MatchTeamInput(club_id="h", club_name="H", formation="4-4-2", players=p_low)
        ratings_low = []
        for i in range(100):
            r = calculate_player_ratings(random.Random(i), team_low, self.away_team, 0, 0, [], [], config)
            # Without bonuses/penalties, player rating is rounded base rating
            ratings_low.append(r["low"])
        
        # Verify spread
        self.assertLess(min(ratings_low), 5.5)
        self.assertGreater(max(ratings_low), 7.5)

        # 2. High consistency player (consistency = 80) should have tight base rating range [6.3, 6.8]
        # (width of 0.5)
        p_high = [create_player("high", "ST1", "ST", 80, consistency=80)]
        team_high = MatchTeamInput(club_id="h", club_name="H", formation="4-4-2", players=p_high)
        ratings_high = []
        for i in range(100):
            r = calculate_player_ratings(random.Random(i), team_high, self.away_team, 0, 0, [], [], config)
            ratings_high.append(r["high"])

        # All high consistency ratings should fall strictly between 6.4 and 6.9
        # (draw modifier = +0.1 added to base range [6.3, 6.8])
        for val in ratings_high:
            self.assertGreaterEqual(val, 6.4)
            self.assertLessEqual(val, 6.9)

    def test_goal_source_distribution_and_attribution(self):
        """Test that goal sources (penalty, set piece, own goal, open play) are correctly rolled and attributed."""
        config = MatchEngineConfig(
            penalty_probability_per_match=0.15,
            set_piece_goal_probability=0.25,
            own_goal_base_probability=0.05,
            own_goal_deficit_multiplier=0.1
        )
        rng = random.Random(12345)

        # Force own goal by increasing probability
        config_og = MatchEngineConfig(
            own_goal_base_probability=1.0,
            penalty_probability_per_match=0.0,
            set_piece_goal_probability=0.0
        )
        og_event = attribute_goal(rng, self.home_team, self.away_team, 10, config_og)
        self.assertEqual(og_event.goal_source, "own_goal")
        self.assertIn("Own Goal!", og_event.description)
        # Own goal scorer must be from defending (away) team
        away_ids = {p.player_id for p in self.away_players}
        self.assertIn(og_event.scorer_id, away_ids)
        self.assertIsNone(og_event.assist_id)

        # Force penalty
        config_pen = MatchEngineConfig(
            own_goal_base_probability=0.0,
            penalty_probability_per_match=1.0,
            set_piece_goal_probability=0.0
        )
        pen_event = attribute_goal(rng, self.home_team, self.away_team, 20, config_pen)
        self.assertEqual(pen_event.goal_source, "penalty")
        self.assertIn("penalty", pen_event.description)
        home_ids = {p.player_id for p in self.home_players}
        self.assertIn(pen_event.scorer_id, home_ids)
        self.assertIsNone(pen_event.assist_id)

        # Force set piece
        config_sp = MatchEngineConfig(
            own_goal_base_probability=0.0,
            penalty_probability_per_match=0.0,
            set_piece_goal_probability=1.0
        )
        sp_event = attribute_goal(rng, self.home_team, self.away_team, 30, config_sp)
        self.assertEqual(sp_event.goal_source, "set_piece")
        self.assertIn("set piece", sp_event.description)
        self.assertIn(sp_event.scorer_id, home_ids)

        # Force open play
        config_op = MatchEngineConfig(
            own_goal_base_probability=0.0,
            penalty_probability_per_match=0.0,
            set_piece_goal_probability=0.0
        )
        op_event = attribute_goal(rng, self.home_team, self.away_team, 40, config_op)
        self.assertEqual(op_event.goal_source, "open_play")
        self.assertIn(op_event.scorer_id, home_ids)
