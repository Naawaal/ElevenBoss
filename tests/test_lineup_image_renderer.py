# tests/test_lineup_image_renderer.py

import unittest
from app.ui.lineup_image_renderer import LineupBoardPlayer, LineupBoardData, render_lineup_board

class TestLineupImageRenderer(unittest.TestCase):
    def setUp(self):
        self.players = [
            LineupBoardPlayer(
                player_id="11111111-1111-1111-1111-111111111111",
                name="Thapa",
                position="ST",
                slot="ST1",
                overall=72,
                fitness=95
            ),
            LineupBoardPlayer(
                player_id="22222222-2222-2222-2222-222222222222",
                name="Very Long Player Name Indeed",
                position="GK",
                slot="GK",
                overall=70,
                fitness=80
            )
        ]
        
    def test_renderer_output_png(self):
        data = LineupBoardData(
            club_name="Kathmandu FC",
            manager_name="Nawal",
            formation="4-4-2",
            chemistry=72,
            average_overall=71.0,
            players=self.players,
            bench_count=7,
            warnings=[]
        )
        
        img_bytes = render_lineup_board(data)
        self.assertIsInstance(img_bytes, bytes)
        
        # Verify PNG file signature (first 8 bytes)
        png_signature = b"\x89PNG\r\n\x1a\n"
        self.assertEqual(img_bytes[:8], png_signature)

    def test_renderer_with_vacant_slots(self):
        # Only GK is provided, ST1 and others are vacant
        data = LineupBoardData(
            club_name="Test FC",
            manager_name="Manager",
            formation="4-4-2",
            chemistry=10,
            average_overall=70.0,
            players=[self.players[1]], # Only GK
            bench_count=0,
            warnings=["Warning: Not enough players to complete XI"]
        )
        
        img_bytes = render_lineup_board(data)
        self.assertIsInstance(img_bytes, bytes)
        self.assertEqual(img_bytes[:8], b"\x89PNG\r\n\x1a\n")
