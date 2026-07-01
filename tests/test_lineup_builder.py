# tests/test_lineup_builder.py

import unittest
from app.engine.lineup_builder import build_auto_lineup

class TestLineupBuilder(unittest.TestCase):
    def setUp(self):
        # Create a squad of 18 players
        self.players = [
            {"id": "p_gk", "display_name": "GK Player", "position": "GK", "overall": 75, "fitness": 100, "is_retired": False},
            
            {"id": "p_lb", "display_name": "LB Player", "position": "LB", "overall": 70, "fitness": 100, "is_retired": False},
            {"id": "p_cb1", "display_name": "CB Player 1", "position": "CB", "overall": 80, "fitness": 100, "is_retired": False},
            {"id": "p_cb2", "display_name": "CB Player 2", "position": "CB", "overall": 78, "fitness": 100, "is_retired": False},
            {"id": "p_rb", "display_name": "RB Player", "position": "RB", "overall": 72, "fitness": 100, "is_retired": False},
            
            {"id": "p_lm", "display_name": "LM Player", "position": "LM", "overall": 74, "fitness": 100, "is_retired": False},
            {"id": "p_cm1", "display_name": "CM Player 1", "position": "CM", "overall": 82, "fitness": 100, "is_retired": False},
            {"id": "p_cm2", "display_name": "CM Player 2", "position": "CM", "overall": 80, "fitness": 100, "is_retired": False},
            {"id": "p_rm", "display_name": "RM Player", "position": "RM", "overall": 73, "fitness": 100, "is_retired": False},
            
            {"id": "p_st1", "display_name": "ST Player 1", "position": "ST", "overall": 85, "fitness": 100, "is_retired": False},
            {"id": "p_st2", "display_name": "ST Player 2", "position": "ST", "overall": 76, "fitness": 100, "is_retired": False},
            
            # Additional bench players
            {"id": "p_sub_gk", "display_name": "Sub GK", "position": "GK", "overall": 60, "fitness": 100, "is_retired": False},
            {"id": "p_sub_cm", "display_name": "Sub CM", "position": "CM", "overall": 70, "fitness": 100, "is_retired": False},
            {"id": "p_sub_st", "display_name": "Sub ST", "position": "ST", "overall": 71, "fitness": 100, "is_retired": False},
            {"id": "p_sub_cb", "display_name": "Sub CB", "position": "CB", "overall": 68, "fitness": 100, "is_retired": False},
            {"id": "p_sub_lb", "display_name": "Sub LB", "position": "LB", "overall": 62, "fitness": 100, "is_retired": False},
            {"id": "p_retired", "display_name": "Retired ST", "position": "ST", "overall": 90, "fitness": 100, "is_retired": True},
        ]

    def test_auto_lineup_builds_valid_starting_xi(self):
        starters, bench, warnings = build_auto_lineup(self.players, "4-4-2")
        
        # Must have exactly 11 starters
        self.assertEqual(len(starters), 11)
        
        # Verify no duplicate players assigned
        starter_ids = [p["id"] for p in starters.values()]
        self.assertEqual(len(starter_ids), len(set(starter_ids)))
        
        # Verify retired player is not selected
        self.assertNotIn("p_retired", starter_ids)
        
        # GK is GK
        self.assertEqual(starters["GK"]["id"], "p_gk")
        
        # Strikers are ST1 and ST2
        self.assertEqual(starters["ST1"]["id"], "p_st1")
        self.assertEqual(starters["ST2"]["id"], "p_st2")

    def test_prefers_natural_positions(self):
        # Add a center back with a very high rating, and check if they're playing CB instead of LB
        starters, bench, warnings = build_auto_lineup(self.players, "4-4-2")
        self.assertEqual(starters["LB"]["id"], "p_lb")
        self.assertEqual(starters["CB1"]["id"], "p_cb1")
        self.assertEqual(starters["CB2"]["id"], "p_cb2")
        self.assertEqual(starters["RB"]["id"], "p_rb")

    def test_bench_selection(self):
        starters, bench, warnings = build_auto_lineup(self.players, "4-4-2")
        
        # Bench players must not duplicate starters
        starter_ids = {p["id"] for p in starters.values()}
        for p in bench:
            self.assertNotIn(p["id"], starter_ids)
            self.assertFalse(p["is_retired"])
            
        # Bench must be sorted by overall rating descending
        overalls = [p["overall"] for p in bench]
        self.assertEqual(overalls, sorted(overalls, reverse=True))

    def test_weak_depth_warning(self):
        # Remove GK from players list
        outfield_only = [p for p in self.players if p["position"] != "GK"]
        starters, bench, warnings = build_auto_lineup(outfield_only, "4-4-2")
        
        # Should contain a warning about GK slot
        gk_warning = [w for w in warnings if "GK" in w]
        self.assertTrue(len(gk_warning) > 0)

if __name__ == "__main__":
    unittest.main()
