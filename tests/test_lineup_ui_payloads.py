# tests/test_lineup_ui_payloads.py

import unittest
import asyncio
from unittest.mock import MagicMock
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

from app.ui.layouts.lineup import build_lineup_layout
from app.ui.components import V2View

class MockPlayer:
    def __init__(self, display_name, overall, position, fitness=100):
        self.display_name = display_name
        self.overall = overall
        self.position = position
        self.fitness = fitness

class TestLineupUiPayloads(unittest.TestCase):
    def setUp(self):
        self.starters = {
            "GK": MockPlayer("GK Player", 75, "GK"),
            "LB": MockPlayer("LB Player", 70, "LB"),
            "CB1": MockPlayer("CB Player 1", 80, "CB"),
            "CB2": MockPlayer("CB Player 2", 78, "CB"),
            "RB": MockPlayer("RB Player", 72, "RB"),
            "LM": MockPlayer("LM Player", 74, "LM"),
            "CM1": MockPlayer("CM Player 1", 82, "CM"),
            "CM2": MockPlayer("CM Player 2", 80, "CM"),
            "RM": MockPlayer("RM Player", 73, "RM"),
            "ST1": MockPlayer("ST Player 1", 85, "ST"),
            "ST2": MockPlayer("ST Player 2", 76, "ST")
        }
        self.bench = [
            MockPlayer("Sub CM", 70, "CM"),
            MockPlayer("Sub ST", 71, "ST")
        ]
        self.warnings = ["Warning: No natural player available for LB."]

    def test_lineup_payload_generation_with_image(self):
        view = build_lineup_layout(
            club_name="Kathmandu FC",
            formation="4-4-2",
            starters=self.starters,
            bench=self.bench,
            warnings=self.warnings,
            is_dirty=True,
            nonce="abc123",
            has_image=True
        )
        
        self.assertTrue(isinstance(view, V2View))
        payload = view.to_components()
        
        # Verify component types: Media Gallery display, Select Menu, Save/Auto-pick Action Row, Navigation Action Row
        self.assertEqual(payload[0]["type"], 12) # Media Gallery
        self.assertEqual(payload[0]["items"][0]["media"], {"url": "attachment://lineup.png"})
        self.assertEqual(payload[0]["items"][0]["description"], "Tactical Lineup Board")
        self.assertEqual(payload[1]["type"], 1)  # Action Row (Select Menu)
        self.assertEqual(payload[2]["type"], 1)  # Action Row (Auto-pick / Save)
        self.assertEqual(payload[3]["type"], 1)  # Action Row (Refresh / Back / Close)

    def test_lineup_payload_generation_fallback(self):
        view = build_lineup_layout(
            club_name="Kathmandu FC",
            formation="4-4-2",
            starters=self.starters,
            bench=self.bench,
            warnings=self.warnings,
            is_dirty=True,
            nonce="abc123",
            has_image=False
        )
        
        self.assertTrue(isinstance(view, V2View))
        payload = view.to_components()
        
        # Verify component types: Container, Select Menu, Save/Auto-pick Action Row, Navigation Action Row
        self.assertEqual(payload[0]["type"], 17) # Container
        self.assertEqual(payload[1]["type"], 1)  # Action Row (Select Menu)
        self.assertEqual(payload[2]["type"], 1)  # Action Row (Auto-pick / Save)
        self.assertEqual(payload[3]["type"], 1)  # Action Row (Refresh / Back / Close)
        
        # Verify text includes club name, formation, and warnings
        text_content = payload[0]["components"][0]["content"]
        self.assertIn("Kathmandu FC", text_content)
        self.assertIn("4-4-2", text_content)
        self.assertIn("Preview (Unsaved Changes)", text_content)
        self.assertIn("Warning: No natural player available", text_content)

    def test_save_button_disabled_when_incomplete(self):
        # Remove a starter to make it incomplete (10 players)
        incomplete_starters = self.starters.copy()
        del incomplete_starters["ST2"]
        
        view = build_lineup_layout(
            club_name="Kathmandu FC",
            formation="4-4-2",
            starters=incomplete_starters,
            bench=self.bench,
            warnings=self.warnings,
            is_dirty=True,
            nonce="abc123",
            has_image=True
        )
        
        payload = view.to_components()
        auto_save_row = payload[2]["components"]
        save_button = auto_save_row[1]
        
        self.assertEqual(save_button["label"], "💾 Save Lineup")
        self.assertTrue(save_button["disabled"])

    def test_save_button_enabled_when_complete(self):
        view = build_lineup_layout(
            club_name="Kathmandu FC",
            formation="4-4-2",
            starters=self.starters,
            bench=self.bench,
            warnings=self.warnings,
            is_dirty=True,
            nonce="abc123",
            has_image=True
        )
        
        payload = view.to_components()
        auto_save_row = payload[2]["components"]
        save_button = auto_save_row[1]
        
        self.assertEqual(save_button["label"], "💾 Save Lineup")
        self.assertFalse(save_button["disabled"])

if __name__ == "__main__":
    unittest.main()
