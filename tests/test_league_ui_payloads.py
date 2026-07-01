import unittest
from unittest.mock import MagicMock
from app.ui.renderers.league_renderer import render_league_dashboard
from app.ui.renderers.table_renderer import render_table
from app.services.league_service import LeagueStatusResult
from app.models.standing import LeagueStanding
from app.models.club import Club
from app.ui.components import V2View

class TestLeagueUiPayloads(unittest.TestCase):
    
    def test_render_league_dashboard_draft_admin(self):
        # League in draft status, user is admin
        data = LeagueStatusResult(
            success=True,
            code="success",
            message="OK",
            league_id=MagicMock(),
            league_name="Championship League",
            status="draft",
            league_size=8,
            human_clubs=3,
            bot_clubs=0,
            season_number=None,
            current_week=None
        )
        
        view = render_league_dashboard(data, nonce="xyz123", is_admin=True)
        self.assertTrue(view.has_components_v2())
        
        components = view.to_components()
        self.assertTrue(len(components) > 0)
        
        # Extract buttons
        buttons = []
        for row in components:
            if row["type"] == 1:  # action_row
                for comp in row["components"]:
                    if comp["type"] == 2:  # button
                        buttons.append(comp)
                        
        # Check Join Button is enabled
        join_btn = next((b for b in buttons if "Join" in b["label"]), None)
        self.assertIsNotNone(join_btn)
        self.assertFalse(join_btn["disabled"])
        
        # Check Start Button is enabled for admin (human_clubs=3 >= 2)
        start_btn = next((b for b in buttons if "Start" in b["label"]), None)
        self.assertIsNotNone(start_btn)
        self.assertFalse(start_btn["disabled"])

    def test_render_league_dashboard_draft_non_admin(self):
        # League in draft status, user is not admin
        data = LeagueStatusResult(
            success=True,
            code="success",
            message="OK",
            league_id=MagicMock(),
            league_name="Championship League",
            status="draft",
            league_size=8,
            human_clubs=3,
            bot_clubs=0,
            season_number=None,
            current_week=None
        )
        
        view = render_league_dashboard(data, nonce="xyz123", is_admin=False)
        components = view.to_components()
        
        buttons = []
        for row in components:
            if row["type"] == 1:  # action_row
                for comp in row["components"]:
                    if comp["type"] == 2:  # button
                        buttons.append(comp)
                        
        # Start Button should be disabled for non-admin
        start_btn = next((b for b in buttons if "Start" in b["label"]), None)
        self.assertIsNotNone(start_btn)
        self.assertTrue(start_btn["disabled"])

    def test_render_league_dashboard_active(self):
        # League in active status
        data = LeagueStatusResult(
            success=True,
            code="success",
            message="OK",
            league_id=MagicMock(),
            league_name="Championship League",
            status="active",
            league_size=8,
            human_clubs=3,
            bot_clubs=5,
            season_number=1,
            current_week=1
        )
        
        view = render_league_dashboard(data, nonce="xyz123", is_admin=True)
        components = view.to_components()
        
        buttons = []
        for row in components:
            if row["type"] == 1:  # action_row
                for comp in row["components"]:
                    if comp["type"] == 2:  # button
                        buttons.append(comp)
                        
        # Join Button must NOT be shown when active
        join_btn = next((b for b in buttons if "Join" in b["label"]), None)
        self.assertIsNone(join_btn)

    def test_render_table(self):
        mock_club = MagicMock(spec=Club)
        mock_club.name = "Stormgate FC"
        
        mock_standing = MagicMock(spec=LeagueStanding)
        mock_standing.club = mock_club
        mock_standing.played = 0
        mock_standing.wins = 0
        mock_standing.draws = 0
        mock_standing.losses = 0
        mock_standing.goals_for = 0
        mock_standing.goals_against = 0
        mock_standing.goal_difference = 0
        mock_standing.points = 0
        
        view = render_table([mock_standing], nonce="xyz123")
        self.assertTrue(view.has_components_v2())
        
        components = view.to_components()
        self.assertTrue(len(components) > 0)
        
        # Verify text display exists and contains Stormgate FC
        container_comp = components[0]
        self.assertEqual(container_comp["type"], 17)  # container
        text_disp = container_comp["components"][0]
        self.assertEqual(text_disp["type"], 10)  # text_display
        self.assertIn("Stormgate FC", text_disp["content"])
