# tests/test_match_event_generator.py

import unittest
import random
from app.engine.match_config import MatchEngineConfig
from app.engine.match_engine import MatchPlayerInput, MatchTeamInput
from app.engine.match_event_generator import (
    attribute_goal,
    generate_goal_events,
    generate_card_events,
    build_timeline
)

def create_player(player_id: str, slot: str, position: str, overall: int) -> MatchPlayerInput:
    return MatchPlayerInput(
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        slot=slot,
        overall=overall,
        potential=overall + 5,
        fitness=100
    )

class TestMatchEventGenerator(unittest.TestCase):
    def setUp(self):
        self.config = MatchEngineConfig()
        self.rng = random.Random(42)
        self.home_players = [
            create_player("h_gk", "GK", "GK", 80),
            create_player("h_cb", "CB1", "CB", 80),
            create_player("h_cm", "CM1", "CM", 80),
            create_player("h_st", "ST1", "ST", 80)
        ]
        self.away_players = [
            create_player("a_gk", "GK", "GK", 80),
            create_player("a_cb", "CB1", "CB", 80),
            create_player("a_cm", "CM1", "CM", 80),
            create_player("a_st", "ST1", "ST", 80)
        ]
        self.home_team = MatchTeamInput("club_h", "Home FC", "4-4-2", self.home_players, is_home=True)
        self.away_team = MatchTeamInput("club_a", "Away FC", "4-4-2", self.away_players, is_home=False)

    def test_goal_attribution_belongs_to_team(self):
        goal = attribute_goal(self.rng, self.home_team, self.away_team, 15, self.config)
        self.assertEqual(goal.club_id, "club_h")
        self.assertIn(goal.scorer_id, [p.player_id for p in self.home_players])
        if goal.assist_id:
            self.assertIn(goal.assist_id, [p.player_id for p in self.home_players])
            self.assertNotEqual(goal.scorer_id, goal.assist_id)

    def test_generate_multiple_goals(self):
        goals = generate_goal_events(self.rng, self.home_team, self.away_team, 3, self.config)
        self.assertEqual(len(goals), 3)
        for i in range(len(goals) - 1):
            self.assertTrue(goals[i].minute <= goals[i+1].minute)

    def test_timeline_sorting_and_structure(self):
        goals = generate_goal_events(self.rng, self.home_team, self.away_team, 1, self.config)
        cards = generate_card_events(self.rng, self.home_team, self.config)
        
        timeline = build_timeline(
            self.home_team,
            self.away_team,
            1,
            0,
            goals,
            cards
        )
        
        self.assertEqual(timeline[0]["type"], "match_start")
        self.assertEqual(timeline[-1]["type"], "full_time")
        
        # Check half time exists
        ht = next((e for e in timeline if e["type"] == "half_time"), None)
        self.assertIsNotNone(ht)
        
        # Check chronological order
        for i in range(len(timeline) - 1):
            self.assertTrue(timeline[i]["minute"] <= timeline[i+1]["minute"])

        # Verify card types in timeline are valid values
        valid_card_types = {"yellow_card", "red_card", "second_yellow_red"}
        for e in timeline:
            if "card" in e["type"] or e["type"] == "second_yellow_red":
                self.assertIn(e["type"], valid_card_types)

