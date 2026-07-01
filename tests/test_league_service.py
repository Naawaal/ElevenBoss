import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid

from app.services.league_service import (
    validate_league_name,
    create_league,
    join_league,
    start_league,
    get_league_status,
    LeagueResult
)
from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.club import Club

class TestLeagueServiceValidation(unittest.TestCase):
    def test_validate_league_name_success(self):
        # Valid names
        self.assertEqual(validate_league_name("Championship Division"), "Championship Division")
        self.assertEqual(validate_league_name("Premier-League 1"), "Premier-League 1")
        self.assertEqual(validate_league_name("O'Connor Shield"), "O'Connor Shield")
        # Whitespace collapse
        self.assertEqual(validate_league_name("  Super   League  "), "Super League")

    def test_validate_league_name_failures(self):
        # Too short
        with self.assertRaises(ValueError):
            validate_league_name("AB")
        # Too long
        with self.assertRaises(ValueError):
            validate_league_name("A" * 41)
        # @everyone
        with self.assertRaises(ValueError):
            validate_league_name("League @everyone")
        # @here
        with self.assertRaises(ValueError):
            validate_league_name("League @here")
        # URLs
        with self.assertRaises(ValueError):
            validate_league_name("http://league.com")
        with self.assertRaises(ValueError):
            validate_league_name("www.league.org")
        with self.assertRaises(ValueError):
            validate_league_name("league.com")
        # Invalid characters
        with self.assertRaises(ValueError):
            validate_league_name("League#1")


class TestLeagueService(unittest.IsolatedAsyncioTestCase):
    
    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_active_or_draft_league_by_guild")
    @patch("app.services.league_service.db_create_league")
    async def test_create_league_success(self, mock_db_create, mock_get_active, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_active.return_value = None
        
        mock_league = MagicMock()
        mock_league.id = uuid.uuid4()
        mock_league.name = "Golden League"
        mock_league.max_clubs = 8
        mock_db_create.return_value = mock_league
        
        res = await create_league("123", "Golden League", 8)
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.league_name, "Golden League")

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_active_or_draft_league_by_guild")
    async def test_create_league_duplicate_rejected(self, mock_get_active, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_active.return_value = MagicMock() # Mock active league exists
        
        res = await create_league("123", "Golden League", 8)
        self.assertFalse(res.success)
        self.assertEqual(res.code, "league_exists")

    async def test_create_league_invalid_size_rejected(self):
        res = await create_league("123", "Golden League", 5) # 5 is invalid size
        self.assertFalse(res.success)
        self.assertEqual(res.code, "invalid_league_size")

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_manager_by_discord_id")
    @patch("app.services.league_service.get_user_club")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.count_league_clubs")
    async def test_join_league_success(self, mock_count, mock_get_draft, mock_get_club, mock_get_manager, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        manager_mock = MagicMock()
        manager_mock.club_id = uuid.uuid4()
        mock_get_manager.return_value = manager_mock
        
        club_mock = MagicMock()
        club_mock.id = manager_mock.club_id
        club_mock.name = "Ironvale FC"
        club_mock.league_id = None
        mock_get_club.return_value = club_mock
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Pro League"
        league_mock.max_clubs = 8
        mock_get_draft.return_value = league_mock
        
        mock_count.return_value = 2 # 2 joined clubs
        
        res = await join_league("123", "456")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(club_mock.league_id, league_mock.id)

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_manager_by_discord_id")
    async def test_join_league_unregistered_rejected(self, mock_get_manager, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_manager.return_value = None # manager doesn't exist
        
        res = await join_league("123", "456")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "not_registered")

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_manager_by_discord_id")
    @patch("app.services.league_service.get_user_club")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.count_league_clubs")
    async def test_join_league_full_rejected(self, mock_count, mock_get_draft, mock_get_club, mock_get_manager, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        manager_mock = MagicMock()
        manager_mock.club_id = uuid.uuid4()
        mock_get_manager.return_value = manager_mock
        
        club_mock = MagicMock()
        club_mock.id = manager_mock.club_id
        club_mock.league_id = None
        mock_get_club.return_value = club_mock
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.max_clubs = 8
        mock_get_draft.return_value = league_mock
        
        mock_count.return_value = 8 # Full!
        
        res = await join_league("123", "456")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "league_full")

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_draft_league_by_guild")
    @patch("app.services.league_service.create_season")
    @patch("app.services.league_service.generate_bot_clubs_for_league")
    @patch("app.services.league_service.initialize_standings")
    async def test_start_league_success(self, mock_standings, mock_generate_bots, mock_create_season, mock_get_draft, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Pro League"
        league_mock.max_clubs = 8
        league_mock.status = LeagueStatus.DRAFT
        mock_get_draft.return_value = league_mock
        
        # Mock 3 joined human clubs
        human_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(3)]
        
        # Execute query returning human clubs
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = human_clubs
        session_mock.execute.return_value = result_mock
        
        # Mock generated bots
        bot_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=True) for _ in range(5)]
        mock_generate_bots.return_value = bot_clubs
        
        season_mock = MagicMock()
        season_mock.id = uuid.uuid4()
        mock_create_season.return_value = season_mock
        
        res = await start_league("123")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.human_clubs, 3)
        self.assertEqual(res.bot_clubs, 5)
        self.assertEqual(league_mock.status, LeagueStatus.ACTIVE)
        
        # Check standings and bots generated counts
        mock_generate_bots.assert_called_once_with(
            session_mock, guild_id="123", league_id=league_mock.id, season_id=season_mock.id, count=5
        )
        mock_standings.assert_called_once()
