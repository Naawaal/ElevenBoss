# tests/test_lineup_validator.py

import unittest
from app.engine.lineup_validator import validate_lineup

class TestLineupValidator(unittest.TestCase):
    def setUp(self):
        # 11 valid players
        self.club_players = [
            {"id": f"p{i}", "display_name": f"P {i}", "position": "CM", "is_retired": False}
            for i in range(15)
        ]
        
        # Build a valid lineup
        self.valid_starters = {
            "GK": "p0",
            "LB": "p1",
            "CB1": "p2",
            "CB2": "p3",
            "RB": "p4",
            "LM": "p5",
            "CM1": "p6",
            "CM2": "p7",
            "RM": "p8",
            "ST1": "p9",
            "ST2": "p10"
        }
        self.valid_bench = ["p11", "p12", "p13"]

    def test_accepts_valid_lineup(self):
        valid, msg = validate_lineup("4-4-2", self.valid_starters, self.valid_bench, self.club_players)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_rejects_unsupported_formation(self):
        valid, msg = validate_lineup("4-2-4", self.valid_starters, self.valid_bench, self.club_players)
        self.assertFalse(valid)
        self.assertIn("Unsupported formation", msg)

    def test_rejects_incorrect_starters_count(self):
        invalid_starters = self.valid_starters.copy()
        del invalid_starters["ST2"]
        
        valid, msg = validate_lineup("4-4-2", invalid_starters, self.valid_bench, self.club_players)
        self.assertFalse(valid)
        self.assertIn("exactly 11 starters", msg)

    def test_rejects_duplicate_players(self):
        invalid_starters = self.valid_starters.copy()
        # Duplicate p0 in ST2
        invalid_starters["ST2"] = "p0"
        
        valid, msg = validate_lineup("4-4-2", invalid_starters, self.valid_bench, self.club_players)
        self.assertFalse(valid)
        self.assertIn("Duplicate players", msg)

    def test_rejects_players_from_another_club(self):
        invalid_starters = self.valid_starters.copy()
        # p99 is from another club (not in club_players)
        invalid_starters["ST2"] = "p99"
        
        valid, msg = validate_lineup("4-4-2", invalid_starters, self.valid_bench, self.club_players)
        self.assertFalse(valid)
        self.assertIn("do not belong to your club", msg)

    def test_rejects_retired_players(self):
        # Retire p0
        players_with_retired = [p.copy() for p in self.club_players]
        players_with_retired[0]["is_retired"] = True
        
        valid, msg = validate_lineup("4-4-2", self.valid_starters, self.valid_bench, players_with_retired)
        self.assertFalse(valid)
        self.assertIn("is retired", msg)

if __name__ == "__main__":
    unittest.main()
