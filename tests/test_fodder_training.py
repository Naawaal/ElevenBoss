import unittest

from apps.discord_bot.cogs.development_cog import CardFusionView


class TestCardFusionView(unittest.TestCase):
    def setUp(self):
        self.mock_players = [
            {"id": "uuid-1", "name": "Lionel Messi", "overall": 90, "level": 1, "position": "FWD", "rarity": "Legendary"},
            {"id": "uuid-2", "name": "Virgil van Dijk", "overall": 88, "level": 2, "position": "DEF", "rarity": "Epic"},
            {"id": "uuid-3", "name": "Alisson", "overall": 85, "level": 1, "position": "GK", "rarity": "Rare"},
            {"id": "uuid-4", "name": "Youth Defender", "overall": 60, "level": 1, "position": "DEF", "rarity": "Common"},
        ]
        self.owner_id = 123456789
        self.view = CardFusionView(self.owner_id, self.mock_players, self.mock_players)

    def test_initial_state(self):
        self.assertEqual(self.view.owner_id, self.owner_id)
        self.assertIsNone(self.view.keeper_id)
        self.assertIsNone(self.view.sacrifice_id)
        self.assertTrue(self.view.confirm_btn.disabled)
        self.assertEqual(len(self.view.keeper_select.options), len(self.mock_players))
        self.assertEqual(len(self.view.sacrifice_select.options), len(self.mock_players))

    def test_select_keeper(self):
        self.view.keeper_id = "uuid-1"
        self.view._rebuild_options()
        self.assertEqual(len(self.view.sacrifice_select.options), 3)
        self.assertNotIn("uuid-1", [opt.value for opt in self.view.sacrifice_select.options])
        self.assertTrue(self.view.confirm_btn.disabled)

    def test_select_sacrifice(self):
        self.view.sacrifice_id = "uuid-4"
        self.view._rebuild_options()
        self.assertEqual(len(self.view.keeper_select.options), 3)
        self.assertNotIn("uuid-4", [opt.value for opt in self.view.keeper_select.options])
        self.assertTrue(self.view.confirm_btn.disabled)

    def test_select_both(self):
        self.view.keeper_id = "uuid-1"
        self.view.sacrifice_id = "uuid-4"
        self.view._rebuild_options()
        self.assertNotIn("uuid-4", [opt.value for opt in self.view.keeper_select.options])
        self.assertNotIn("uuid-1", [opt.value for opt in self.view.sacrifice_select.options])
        self.assertFalse(self.view.confirm_btn.disabled)
