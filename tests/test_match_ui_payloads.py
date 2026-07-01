# tests/test_match_ui_payloads.py

import unittest
import asyncio
from unittest.mock import MagicMock

# discord.ui.View requires a running event loop when instantiated.
# Patch it before any discord imports to allow V2View to work in tests.
_mock_loop = MagicMock()
_mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=_mock_loop)


from app.services.matchday_service import MatchdayStatusResult, MatchdayRunResult, MatchdayFixtureResult
from app.services.match_service import MatchDetailResult
from app.ui.layouts.matchday import build_matchday_status_layout, build_matchday_run_layout
from app.ui.layouts.match import build_match_detail_layout
from app.ui.components import V2View

NONCE = "nonce_123"

class TestMatchUiPayloads(unittest.TestCase):

    def test_matchday_status_payload_renders_admin_ready(self):
        """build_matchday_status_layout returns a valid V2View with active controls for admin."""
        data = MatchdayStatusResult(
            success=True,
            code="success",
            message="OK",
            league_name="Super League",
            season_number=1,
            current_week=1,
            total_fixtures=4,
            scheduled_fixtures=4,
            played_fixtures=0,
            status_label="Ready"
        )
        
        view = build_matchday_status_layout(data, NONCE, is_admin=True)
        self.assertIsInstance(view, V2View)
        components = view.to_components()
        self.assertTrue(len(components) > 0)
        
        # Check that Simulate button is present and not disabled
        buttons = []
        for row in components:
            if row["type"] == 1:  # action_row
                for comp in row["components"]:
                    if comp["type"] == 2:  # button
                        buttons.append(comp)
                        
        simulate_btn = next((b for b in buttons if "Simulate" in b["label"]), None)
        self.assertIsNotNone(simulate_btn)
        self.assertFalse(simulate_btn["disabled"])

    def test_matchday_status_payload_renders_non_admin_disabled(self):
        """build_matchday_status_layout does not include the run button for non-admins."""
        data = MatchdayStatusResult(
            success=True,
            code="success",
            message="OK",
            league_name="Super League",
            season_number=1,
            current_week=1,
            total_fixtures=4,
            scheduled_fixtures=4,
            played_fixtures=0,
            status_label="Ready"
        )
        
        view = build_matchday_status_layout(data, NONCE, is_admin=False)
        components = view.to_components()
        
        buttons = []
        for row in components:
            if row["type"] == 1:  # action_row
                for comp in row["components"]:
                    if comp["type"] == 2:  # button
                        buttons.append(comp)
                        
        simulate_btn = next((b for b in buttons if "Simulate" in b["label"]), None)
        self.assertIsNone(simulate_btn)  # Run button hidden for non-admin

    def test_matchday_status_payload_disabled_when_complete(self):
        """build_matchday_status_layout disables the run button if status is Season Complete."""
        data = MatchdayStatusResult(
            success=True,
            code="success",
            message="OK",
            league_name="Super League",
            season_number=1,
            current_week=5,
            total_fixtures=4,
            scheduled_fixtures=0,
            played_fixtures=4,
            status_label="Season Complete"
        )
        
        view = build_matchday_status_layout(data, NONCE, is_admin=True)
        components = view.to_components()
        
        buttons = []
        for row in components:
            if row["type"] == 1:  # action_row
                for comp in row["components"]:
                    if comp["type"] == 2:  # button
                        buttons.append(comp)
                        
        simulate_btn = next((b for b in buttons if "Simulate" in b["label"]), None)
        self.assertIsNotNone(simulate_btn)
        self.assertTrue(simulate_btn["disabled"])

    def test_matchday_run_payload_renders(self):
        """build_matchday_run_layout renders the list of scores and navigation controls."""
        fixture_res = [
            MatchdayFixtureResult("f1", "FC Kathmandu", "Ironvale Rovers", 2, 1, "played"),
            MatchdayFixtureResult("f2", "Stormgate FC", "Riverside City", 0, 0, "played")
        ]
        data = MatchdayRunResult(
            success=True,
            code="success",
            message="Simulated successfully",
            league_name="Championship League",
            season_number=1,
            simulated_week=1,
            results=fixture_res,
            table_updated=True,
            season_completed=False
        )
        
        view = build_matchday_run_layout(data, NONCE)
        self.assertIsInstance(view, V2View)
        components = view.to_components()
        self.assertTrue(len(components) > 0)
        
        # Verify text display exists and lists results
        container_comp = components[0]
        self.assertEqual(container_comp["type"], 17)  # container
        text_disp = container_comp["components"][0]
        self.assertEqual(text_disp["type"], 10)  # text_display
        self.assertIn("FC Kathmandu", text_disp["content"])
        self.assertIn("Riverside City", text_disp["content"])
        self.assertIn("advanced to **Week 2**", text_disp["content"])

    def test_match_detail_payload_renders(self):
        """build_match_detail_layout renders header, stats, and timeline properly."""
        timeline = [
            {"minute": 0, "type": "match_start", "description": "Match started!"},
            {"minute": 12, "type": "goal", "description": "Goal scored by R. Thapa!"},
            {"minute": 45, "type": "half_time", "description": "Halftime score 1-0."},
            {"minute": 70, "type": "yellow_card", "description": "Yellow card to defender."},
            {"minute": 90, "type": "full_time", "description": "Match ended."}
        ]
        data = MatchDetailResult(
            success=True,
            code="success",
            message="OK",
            fixture_id="fixture_id_123",
            home_club_name="Kathmandu FC",
            away_club_name="Ironvale FC",
            home_goals=2,
            away_goals=1,
            home_possession=55,
            away_possession=45,
            home_shots=12,
            away_shots=8,
            home_shots_on_target=6,
            away_shots_on_target=4,
            motm_player_name="R. Thapa",
            timeline=timeline
        )
        
        view = build_match_detail_layout(data, NONCE)
        self.assertIsInstance(view, V2View)
        components = view.to_components()
        self.assertTrue(len(components) > 0)
        
        # Verify header content
        text_comp = components[0]["components"][0]
        self.assertIn("Kathmandu FC", text_comp["content"])
        self.assertIn("R. Thapa", text_comp["content"])
        
        # Verify timeline content
        timeline_comp = components[2]["components"][0]
        self.assertIn("Goal scored by R. Thapa", timeline_comp["content"])
        self.assertIn("Match ended", timeline_comp["content"])

    def test_match_detail_payload_renders_empty_events(self):
        """build_match_detail_layout renders safely if match timeline is empty."""
        data = MatchDetailResult(
            success=True,
            code="success",
            message="OK",
            fixture_id="fixture_id_123",
            home_club_name="Super Long Named Club Kathmandu FC",
            away_club_name="Ironvale FC",
            home_goals=0,
            away_goals=0,
            home_possession=50,
            away_possession=50,
            home_shots=0,
            away_shots=0,
            home_shots_on_target=0,
            away_shots_on_target=0,
            motm_player_name="None",
            timeline=[]
        )
        
        view = build_match_detail_layout(data, NONCE)
        self.assertIsNotNone(view)
        components = view.to_components()
        
        timeline_comp = components[2]["components"][0]
        self.assertIn("No significant events occurred", timeline_comp["content"])
