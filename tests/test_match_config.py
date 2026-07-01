# tests/test_match_config.py

import unittest
from app.engine.match_config import MatchEngineConfig

class TestMatchConfig(unittest.TestCase):
    def test_default_config_values(self):
        config = MatchEngineConfig()
        self.assertEqual(config.base_xg, 1.30)
        self.assertEqual(config.home_advantage_xg, 0.20)
        self.assertEqual(config.min_xg, 0.20)
        self.assertEqual(config.max_xg, 4.00)
        self.assertEqual(config.randomness_factor, 0.22)
        self.assertEqual(config.max_common_goals, 5)
        
        self.assertEqual(config.yellow_card_base_rate, 0.18)
        self.assertEqual(config.red_card_base_rate, 0.02)
        
        self.assertEqual(config.possession_delta_multiplier, 0.4)
        self.assertEqual(config.min_possession, 35)
        self.assertEqual(config.max_possession, 65)

    def test_config_overrides(self):
        config = MatchEngineConfig(base_xg=1.5, min_xg=0.1)
        self.assertEqual(config.base_xg, 1.5)
        self.assertEqual(config.min_xg, 0.1)
        # Undefined overrides should remain default
        self.assertEqual(config.max_xg, 4.00)
