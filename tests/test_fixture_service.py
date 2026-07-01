"""
Tests for the Fixture Service.

All external dependencies (database, repositories) are mocked.
Tests verify business logic, validation order, and result codes.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid

from app.services.fixture_service import (
    get_current_week_fixtures,
    get_fixtures_for_week,
    FixtureListResult,
)


def make_mock_league(name="Test League", status="active"):
    league = MagicMock()
    league.id = uuid.uuid4()
    league.name = name
    league.status = status
    return league


def make_mock_season(season_number=1, current_week=1):
    season = MagicMock()
    season.id = uuid.uuid4()
    season.season_number = season_number
    season.current_week = current_week
    return season


def make_mock_clubs(n: int, season_id: uuid.UUID):
    clubs = []
    for i in range(n):
        club = MagicMock()
        club.id = uuid.uuid4()
        club.season_id = season_id
        clubs.append(club)
    return clubs


# ── Get Current Week Fixtures Tests ───────────────────────────────

class TestGetCurrentWeekFixtures(unittest.IsolatedAsyncioTestCase):

    @patch("app.services.fixture_service.get_session")
    @patch("app.services.fixture_service.get_active_league_by_guild")
    @patch("app.services.fixture_service.get_active_season_for_league")
    @patch("app.services.fixture_service.get_fixture_week_range")
    @patch("app.services.fixture_service.get_fixtures_for_active_week")
    async def test_returns_current_week_fixtures(
        self, mock_fixtures, mock_range, mock_season, mock_league, mock_session
    ):
        """Current week fixtures are returned correctly."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        mock_league.return_value = make_mock_league()
        season = make_mock_season(season_number=1, current_week=3)
        mock_season.return_value = season
        mock_range.return_value = (1, 7)

        # Mock 4 fixtures for week 3
        mock_fixtures.return_value = [MagicMock() for _ in range(4)]

        result = await get_current_week_fixtures("guild_123")

        self.assertTrue(result.success)
        self.assertEqual(result.selected_week, 3)
        self.assertEqual(result.current_week, 3)
        self.assertEqual(result.min_week, 1)
        self.assertEqual(result.max_week, 7)
        self.assertEqual(len(result.fixtures), 4)

    @patch("app.services.fixture_service.get_session")
    @patch("app.services.fixture_service.get_active_league_by_guild")
    @patch("app.services.fixture_service.get_active_season_for_league")
    @patch("app.services.fixture_service.get_fixture_week_range")
    async def test_returns_not_generated_if_no_fixtures(
        self, mock_range, mock_season, mock_league, mock_session
    ):
        """Returns fixtures_missing code when week range is None."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        mock_league.return_value = make_mock_league()
        mock_season.return_value = make_mock_season()
        mock_range.return_value = None  # No fixtures generated

        result = await get_current_week_fixtures("guild_123")

        self.assertFalse(result.success)
        self.assertEqual(result.code, "fixtures_missing")


# ── Get Fixtures For Week Tests ────────────────────────────────────

class TestGetFixturesForWeek(unittest.IsolatedAsyncioTestCase):

    @patch("app.services.fixture_service.get_session")
    @patch("app.services.fixture_service.get_active_league_by_guild")
    @patch("app.services.fixture_service.get_active_season_for_league")
    @patch("app.services.fixture_service.get_fixture_week_range")
    @patch("app.services.fixture_service.get_fixtures_by_week")
    async def test_valid_week_returns_fixtures(
        self, mock_fixtures, mock_range, mock_season, mock_league, mock_session
    ):
        """A valid week request returns the correct fixtures."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        mock_league.return_value = make_mock_league()
        mock_season.return_value = make_mock_season(current_week=1)
        mock_range.return_value = (1, 7)
        mock_fixtures.return_value = [MagicMock() for _ in range(4)]

        result = await get_fixtures_for_week("guild_123", week=5)

        self.assertTrue(result.success)
        self.assertEqual(result.selected_week, 5)

    @patch("app.services.fixture_service.get_session")
    @patch("app.services.fixture_service.get_active_league_by_guild")
    @patch("app.services.fixture_service.get_active_season_for_league")
    @patch("app.services.fixture_service.get_fixture_week_range")
    async def test_invalid_week_too_high_rejected(
        self, mock_range, mock_season, mock_league, mock_session
    ):
        """Week number beyond max_week returns invalid_week code."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        mock_league.return_value = make_mock_league()
        mock_season.return_value = make_mock_season()
        mock_range.return_value = (1, 7)

        result = await get_fixtures_for_week("guild_123", week=99)

        self.assertFalse(result.success)
        self.assertEqual(result.code, "invalid_week")

    @patch("app.services.fixture_service.get_session")
    @patch("app.services.fixture_service.get_active_league_by_guild")
    @patch("app.services.fixture_service.get_active_season_for_league")
    @patch("app.services.fixture_service.get_fixture_week_range")
    async def test_invalid_week_too_low_rejected(
        self, mock_range, mock_season, mock_league, mock_session
    ):
        """Week number below min_week returns invalid_week code."""
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        mock_league.return_value = make_mock_league()
        mock_season.return_value = make_mock_season()
        mock_range.return_value = (1, 7)

        result = await get_fixtures_for_week("guild_123", week=0)

        self.assertFalse(result.success)
        self.assertEqual(result.code, "invalid_week")


if __name__ == "__main__":
    unittest.main()
