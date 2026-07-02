# tests/test_matchday_service.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from app.services.matchday_service import MatchdayService
from app.models.fixture import FixtureStatus
from app.models.season import SeasonStatus
from app.models.league import LeagueStatus
from app.models.scheduler_run import SchedulerRunStatus
from app.models.player import Player
from app.models.lineup import Lineup, LineupPlayer


class TestMatchdayService(unittest.IsolatedAsyncioTestCase):

    @patch("app.services.matchday_service.get_session")
    @patch("app.services.matchday_service.get_active_league_by_guild")
    @patch("app.services.matchday_service.get_active_season_for_league")
    @patch("app.services.matchday_service.get_week_fixture_counts")
    async def test_get_matchday_status_success(self, mock_counts, mock_season, mock_league, mock_session):
        """get_matchday_status returns correct counts and label when active."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        league = MagicMock()
        league.name = "Championship"
        league.status = LeagueStatus.ACTIVE
        mock_league.return_value = league

        season = MagicMock()
        season.season_number = 1
        season.current_week = 3
        season.status = SeasonStatus.ACTIVE
        mock_season.return_value = season

        mock_counts.return_value = {"total": 4, "scheduled": 3, "played": 1}

        res = await MatchdayService.get_matchday_status("123")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.total_fixtures, 4)
        self.assertEqual(res.scheduled_fixtures, 3)
        self.assertEqual(res.played_fixtures, 1)
        self.assertEqual(res.status_label, "Ready")

    @patch("app.services.matchday_service.get_session")
    async def test_run_matchday_rejects_non_admin(self, mock_session):
        """run_current_matchday returns permission_denied for non-admin."""
        res = await MatchdayService.run_current_matchday("123", "user_123", is_admin=False)
        self.assertFalse(res.success)
        self.assertEqual(res.code, "permission_denied")

    @patch("app.services.matchday_service.get_session")
    @patch("app.services.matchday_service.get_active_league_by_guild")
    async def test_run_matchday_rejects_missing_league(self, mock_league, mock_session):
        """run_current_matchday returns league_not_found if no active league exists."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock
        mock_league.return_value = None

        res = await MatchdayService.run_current_matchday("123", "user_123", is_admin=True)
        self.assertFalse(res.success)
        self.assertEqual(res.code, "league_not_found")

    @patch("app.services.matchday_service.get_session")
    @patch("app.services.matchday_service.get_active_league_by_guild")
    @patch("app.services.matchday_service.get_active_season_for_league")
    @patch("app.services.matchday_service.get_job_by_key")
    @patch("app.services.matchday_service.create_running_job")
    @patch("app.services.matchday_service.get_current_week_fixtures_for_update")
    @patch("app.services.matchday_service.mark_job_failed")
    async def test_run_matchday_rejects_empty_fixtures(
        self, mock_job_fail, mock_fixtures, mock_create_job, mock_job, mock_season, mock_league, mock_session
    ):
        """run_current_matchday rejects if no fixtures exist for current week."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        league = MagicMock()
        mock_league.return_value = league
        season = MagicMock(id=uuid.uuid4(), current_week=1, season_number=1)
        mock_season.return_value = season

        mock_job.return_value = None  # No previous job
        mock_create_job.return_value = MagicMock()

        mock_fixtures.return_value = []  # No fixtures found

        res = await MatchdayService.run_current_matchday("123", "user_123", is_admin=True)
        self.assertFalse(res.success)
        self.assertEqual(res.code, "fixtures_not_found")
        mock_job_fail.assert_called_once()

    @patch("app.services.matchday_service.get_session")
    @patch("app.services.matchday_service.get_active_league_by_guild")
    @patch("app.services.matchday_service.get_active_season_for_league")
    @patch("app.services.matchday_service.get_job_by_key")
    async def test_run_matchday_rejects_already_played(self, mock_job, mock_season, mock_league, mock_session):
        """run_current_matchday rejects duplicate run if job key was successful."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        league = MagicMock()
        mock_league.return_value = league
        season = MagicMock(id=uuid.uuid4(), current_week=1)
        mock_season.return_value = season

        job = MagicMock()
        job.status = SchedulerRunStatus.SUCCESS
        mock_job.return_value = job

        res = await MatchdayService.run_current_matchday("123", "user_123", is_admin=True)
        self.assertFalse(res.success)
        self.assertEqual(res.code, "matchday_already_played")

    @patch("app.services.matchday_service.get_session")
    @patch("app.services.matchday_service.get_active_league_by_guild")
    @patch("app.services.matchday_service.get_active_season_for_league")
    @patch("app.services.matchday_service.get_job_by_key")
    @patch("app.services.matchday_service.create_running_job")
    @patch("app.services.matchday_service.get_current_week_fixtures_for_update")
    @patch("app.services.matchday_service.get_clubs_in_league")
    @patch("app.services.matchday_service.get_active_lineup")
    @patch("app.services.matchday_service.get_players_by_club_id")
    @patch("app.services.matchday_service.save_lineup_with_players")
    @patch("app.services.matchday_service.create_match_result")
    @patch("app.services.matchday_service.bulk_create_match_events")
    @patch("app.services.matchday_service.get_standing_for_update")
    @patch("app.services.matchday_service.get_fixture_week_range")
    @patch("app.services.matchday_service.mark_job_success")
    @patch("app.services.matchday_service.mark_job_failed")
    @patch("app.services.matchday_service.mark_fixture_played")
    async def test_run_matchday_success_with_lineup_fallbacks(
        self, mock_fixture_play, mock_job_fail, mock_job_ok, mock_week_range, mock_standing, mock_events, mock_result,
        mock_save_lineup, mock_players, mock_lineup, mock_get_clubs, mock_fixtures, mock_create_job, mock_job, mock_season, mock_league, mock_session
    ):
        """run_current_matchday simulates, creates events, updates standings, advances week, and handles fallback lineups."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        league = MagicMock()
        league.name = "Pro League"
        mock_league.return_value = league

        season = MagicMock(id=uuid.uuid4(), current_week=2, season_number=1)
        mock_season.return_value = season

        mock_job.return_value = None
        mock_create_job.return_value = MagicMock()

        # 1 fixture
        home_club = MagicMock(id=uuid.uuid4(), name="Home FC")
        home_club.is_bot_controlled = False
        away_club = MagicMock(id=uuid.uuid4(), name="Away FC")
        away_club.is_bot_controlled = False
        mock_get_clubs.return_value = [home_club, away_club]
        fixture = MagicMock(id=uuid.uuid4(), home_club=home_club, away_club=away_club, status=FixtureStatus.SCHEDULED)
        mock_fixtures.return_value = [fixture]

        # Use actual model objects to avoid nested mocking problems
        home_players = []
        away_players = []
        for i in range(11):
            hp = Player(
                id=uuid.uuid4(),
                display_name=f"H Player {i}",
                position="CM" if i > 0 else "GK",
                overall=80,
                potential=85,
                fitness=100,
                is_retired=False
            )
            ap = Player(
                id=uuid.uuid4(),
                display_name=f"A Player {i}",
                position="CM" if i > 0 else "GK",
                overall=70,
                potential=75,
                fitness=100,
                is_retired=False
            )
            home_players.append(hp)
            away_players.append(ap)

        # Setup real lineup players
        slots = ["GK", "LB", "CB1", "CB2", "RB", "LM", "CM1", "CM2", "RM", "ST1", "ST2"]
        
        home_lineup = Lineup(formation="4-4-2", is_active=True)
        home_lps = []
        for slot, p in zip(slots, home_players):
            lp = LineupPlayer(is_starter=True, slot=slot, player_id=p.id, player=p)
            home_lps.append(lp)
        home_lineup.lineup_players = home_lps

        away_lineup = Lineup(formation="4-4-2", is_active=True)
        away_lps = []
        for slot, p in zip(slots, away_players):
            lp = LineupPlayer(is_starter=True, slot=slot, player_id=p.id, player=p)
            away_lps.append(lp)
        away_lineup.lineup_players = away_lps

        # Home team has lineup, away team does not (triggers fallback)
        mock_lineup.side_effect = [
            home_lineup,   # Home lineup
            None,          # Away lineup (None -> triggers auto pick best XI)
            away_lineup    # Eagerly loaded after save lineup
        ]

        mock_players.side_effect = [
            home_players,  # Home players
            away_players   # Away club players
        ]

        mock_save_lineup.return_value = away_lineup

        # Standings mocks
        home_standing = MagicMock(played=0, wins=0, draws=0, losses=0, goals_for=0, goals_against=0, goal_difference=0, points=0)
        away_standing = MagicMock(played=0, wins=0, draws=0, losses=0, goals_for=0, goals_against=0, goal_difference=0, points=0)
        mock_standing.side_effect = [home_standing, away_standing]

        # Fixture weeks max_week=5
        mock_week_range.return_value = (1, 5)

        res = await MatchdayService.run_current_matchday("123", "user_123", is_admin=True)
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.simulated_week, 2)
        self.assertEqual(len(res.results), 1)
        self.assertEqual(season.current_week, 3)  # Advanced week

        mock_fixture_play.assert_called_once()
        mock_result.assert_called_once()
        mock_events.assert_called_once()
        mock_job_ok.assert_called_once()
