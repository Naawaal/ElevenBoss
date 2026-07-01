"""
Tests for starting the league and verifying automatic fixture generation.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid

from app.services.league_service import start_league
from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.club import Club


class TestLeagueStartWithFixtures(unittest.IsolatedAsyncioTestCase):

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.get_active_league_by_guild")
    @patch("app.services.league_service.get_active_season_for_league")
    @patch("app.services.league_service.create_season")
    @patch("app.services.league_service.generate_bot_clubs_for_league")
    @patch("app.services.league_service.initialize_standings")
    @patch("app.services.league_service.bulk_create_fixtures")
    async def test_league_start_generates_fixtures_for_8_clubs(
        self, mock_bulk, mock_standings, mock_generate_bots, mock_create_season,
        mock_active_season, mock_active_league, mock_get_draft, mock_get_session
    ):
        """Starting a league with 8 clubs automatically generates 28 fixtures across 7 weeks."""
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock

        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Golden League"
        league_mock.max_clubs = 8
        league_mock.status = LeagueStatus.DRAFT
        mock_get_draft.return_value = league_mock
        mock_active_season.return_value = None

        # 3 human clubs
        human_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(3)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = human_clubs
        session_mock.execute.return_value = result_mock

        # 5 bot clubs
        bot_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=True) for _ in range(5)]
        mock_generate_bots.return_value = bot_clubs

        season_mock = MagicMock()
        season_mock.id = uuid.uuid4()
        mock_create_season.return_value = season_mock

        res = await start_league("123")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.total_clubs, 8)
        self.assertEqual(res.total_weeks, 7)
        self.assertEqual(res.total_fixtures, 28)
        self.assertEqual(res.fixtures_per_week, 4)

        # Assert fixtures were actually bulk created
        mock_bulk.assert_called_once()
        created_fixtures = mock_bulk.call_args[0][1]
        self.assertEqual(len(created_fixtures), 28)
        # Check that they have the right properties
        for f in created_fixtures:
            self.assertEqual(f.guild_id, "123")
            self.assertEqual(f.season_id, season_mock.id)
            self.assertTrue(1 <= f.week <= 7)

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.get_active_league_by_guild")
    @patch("app.services.league_service.get_active_season_for_league")
    @patch("app.services.league_service.create_season")
    @patch("app.services.league_service.generate_bot_clubs_for_league")
    @patch("app.services.league_service.initialize_standings")
    @patch("app.services.league_service.bulk_create_fixtures")
    async def test_league_start_generates_fixtures_for_16_clubs(
        self, mock_bulk, mock_standings, mock_generate_bots, mock_create_season,
        mock_active_season, mock_active_league, mock_get_draft, mock_get_session
    ):
        """Starting a league with 16 clubs automatically generates 120 fixtures across 15 weeks."""
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock

        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Super 16 League"
        league_mock.max_clubs = 16
        league_mock.status = LeagueStatus.DRAFT
        mock_get_draft.return_value = league_mock
        mock_active_season.return_value = None

        # 6 human clubs
        human_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(6)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = human_clubs
        session_mock.execute.return_value = result_mock

        # 10 bot clubs
        bot_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=True) for _ in range(10)]
        mock_generate_bots.return_value = bot_clubs

        season_mock = MagicMock()
        season_mock.id = uuid.uuid4()
        mock_create_season.return_value = season_mock

        res = await start_league("123")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.total_clubs, 16)
        self.assertEqual(res.total_weeks, 15)
        self.assertEqual(res.total_fixtures, 120)
        self.assertEqual(res.fixtures_per_week, 8)

        mock_bulk.assert_called_once()
        created_fixtures = mock_bulk.call_args[0][1]
        self.assertEqual(len(created_fixtures), 120)

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.get_active_league_by_guild")
    @patch("app.services.league_service.get_active_season_for_league")
    @patch("app.services.league_service.create_season")
    @patch("app.services.league_service.generate_bot_clubs_for_league")
    @patch("app.services.league_service.initialize_standings")
    @patch("app.services.league_service.bulk_create_fixtures")
    async def test_league_start_rollback_if_fixture_insert_fails(
        self, mock_bulk, mock_standings, mock_generate_bots, mock_create_season,
        mock_active_season, mock_active_league, mock_get_draft, mock_get_session
    ):
        """If fixture bulk insert fails, start_league returns database_error and transaction rolls back."""
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock

        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Pro League"
        league_mock.max_clubs = 8
        league_mock.status = LeagueStatus.DRAFT
        mock_get_draft.return_value = league_mock
        mock_active_season.return_value = None

        human_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(4)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = human_clubs
        session_mock.execute.return_value = result_mock

        bot_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=True) for _ in range(4)]
        mock_generate_bots.return_value = bot_clubs

        season_mock = MagicMock()
        season_mock.id = uuid.uuid4()
        mock_create_season.return_value = season_mock

        # Simulate exception during bulk insert
        mock_bulk.side_effect = RuntimeError("DB insert failure")

        res = await start_league("123")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "database_error")

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.get_active_league_by_guild")
    @patch("app.services.league_service.get_active_season_for_league")
    async def test_league_start_rejects_if_already_active(
        self, mock_active_season, mock_active_league, mock_get_draft, mock_get_session
    ):
        """Starting a league that's already active returns league_already_active."""
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_draft.return_value = None  # No draft league
        mock_active_league.return_value = MagicMock()  # Active league exists

        res = await start_league("123")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "league_already_active")


if __name__ == "__main__":
    unittest.main()
