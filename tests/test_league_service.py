# tests/test_league_service.py

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from zoneinfo import ZoneInfo

from app.models.league import League, LeagueStatus
from app.services.league_service import (
    validate_league_name,
    create_league,
    join_league,
    start_league,
    extend_deadline,
    cancel_league,
    update_league_configuration,
    LeagueResult
)

class TestLeagueNameValidation(unittest.TestCase):
    def test_valid_league_names(self):
        self.assertEqual(validate_league_name("Champions League"), "Champions League")
        self.assertEqual(validate_league_name("Tier-1 League"), "Tier-1 League")
        self.assertEqual(validate_league_name("Manager's Cup"), "Manager's Cup")
        self.assertEqual(validate_league_name("  Trimmed Name  "), "Trimmed Name")

    def test_invalid_league_names(self):
        # Length constraints
        with self.assertRaises(ValueError):
            validate_league_name("Ab")
        with self.assertRaises(ValueError):
            validate_league_name("A" * 41)
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
    @patch("app.services.league_service.get_non_terminal_league_by_guild")
    @patch("app.services.league_service.db_create_league")
    async def test_create_league_success(self, mock_db_create, mock_get_non_terminal, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_non_terminal.return_value = None
        
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
    @patch("app.services.league_service.get_non_terminal_league_by_guild")
    async def test_create_league_duplicate_rejected(self, mock_get_non_terminal, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_non_terminal.return_value = MagicMock() # Mock active/draft league exists
        
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
    @patch("app.services.league_service.get_latest_league_for_update")
    @patch("app.services.league_service.count_league_clubs")
    async def test_join_league_success(self, mock_count, mock_get_latest, mock_get_club, mock_get_manager, mock_get_session):
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
        league_mock.status = LeagueStatus.DRAFT
        league_mock.target_club_count = 8
        league_mock.registration_deadline_at = None
        mock_get_latest.return_value = league_mock
        
        mock_count.return_value = 2
        
        res = await join_league("123", "456")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(club_mock.league_id, league_mock.id)

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_manager_by_discord_id")
    @patch("app.services.league_service.get_latest_league_for_update")
    async def test_join_league_unregistered_rejected(self, mock_get_latest, mock_get_manager, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_get_manager.return_value = None # manager doesn't exist
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.status = LeagueStatus.DRAFT
        league_mock.registration_deadline_at = None
        mock_get_latest.return_value = league_mock
        
        res = await join_league("123", "456")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "not_registered")

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.get_manager_by_discord_id")
    @patch("app.services.league_service.get_user_club")
    @patch("app.services.league_service.get_latest_league_for_update")
    @patch("app.services.league_service.count_league_clubs")
    async def test_join_league_full_rejected(self, mock_count, mock_get_latest, mock_get_club, mock_get_manager, mock_get_session):
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
        league_mock.status = LeagueStatus.DRAFT
        league_mock.target_club_count = 8
        league_mock.registration_deadline_at = None
        mock_get_latest.return_value = league_mock
        
        mock_count.return_value = 8 # Full!
        
        res = await join_league("123", "456")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "league_full")


    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.claim_league_for_starting")
    @patch("app.services.league_service.get_active_league_by_guild")
    @patch("app.services.league_service.create_season")
    @patch("app.services.league_service.generate_bot_clubs_for_league")
    @patch("app.services.league_service.initialize_standings")
    @patch("app.services.league_service.bulk_create_fixtures")
    async def test_start_league_success(self, mock_bulk, mock_standings, mock_generate_bots, mock_create_season, mock_active_league, mock_claim_league, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock

        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Pro League"
        league_mock.target_club_count = 8
        league_mock.fill_bots_after_deadline = True
        league_mock.minimum_human_clubs = 2
        league_mock.status = LeagueStatus.DRAFT
        
        mock_claim_league.return_value = league_mock
        mock_active_league.return_value = None

        # Mock 3 joined human clubs
        human_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(3)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = human_clubs
        session_mock.execute.return_value = result_mock

        # Mock generated bots
        bot_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=True) for _ in range(5)]
        mock_generate_bots.return_value = bot_clubs

        season_mock = MagicMock()
        season_mock.id = uuid.uuid4()
        mock_create_season.return_value = season_mock

        mock_bulk.return_value = []

        res = await start_league("123")
        self.assertTrue(res.success)
        self.assertEqual(res.code, "success")
        self.assertEqual(res.human_clubs, 3)
        self.assertEqual(res.bot_clubs, 5)
        self.assertEqual(res.total_clubs, 8)
        self.assertEqual(league_mock.status, LeagueStatus.ACTIVE)

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.claim_league_for_starting")
    @patch("app.services.league_service.get_active_league_by_guild")
    async def test_start_league_rejects_already_active_league(self, mock_active_league, mock_claim_league, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        mock_claim_league.return_value = None  # Already started/starting
        mock_active_league.return_value = MagicMock()  # Active league exists

        res = await start_league("123")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "league_already_active")

        
    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.parse_deadline_to_utc")
    @patch("app.services.announcement_service.AnnouncementService.send_announcement")
    async def test_extend_deadline_success_actual(self, mock_announce, mock_parse_deadline, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        from datetime import timedelta
        future_time = datetime.now(timezone.utc) + timedelta(days=1)
        mock_parse_deadline.return_value = future_time
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Pro League"
        league_mock.status = LeagueStatus.NEEDS_ADMIN_REVIEW
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = league_mock
        session_mock.execute.return_value = result_mock
        
        res = await extend_deadline("123", "Sunday 20:00")
        self.assertTrue(res.success)
        self.assertEqual(league_mock.status, LeagueStatus.DRAFT)
        self.assertEqual(league_mock.registration_deadline_at, future_time)
        mock_announce.assert_called_once()

    @patch("app.services.league_service.get_session")
    @patch("app.services.announcement_service.AnnouncementService.notify_users_dm")
    @patch("app.services.announcement_service.AnnouncementService.send_announcement")
    async def test_cancel_league_success(self, mock_announce, mock_dm, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Pro League"
        league_mock.status = LeagueStatus.DRAFT
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = league_mock
        
        # Mock seasons query
        result_seasons_mock = MagicMock()
        result_seasons_mock.scalars.return_value.all.return_value = []
        
        # Mock joined managers
        result_users_mock = MagicMock()
        result_users_mock.scalars.return_value.all.return_value = [555]
        
        session_mock.execute.side_effect = [result_mock, result_seasons_mock, result_users_mock]
        
        res = await cancel_league("123")
        self.assertTrue(res.success)
        self.assertEqual(league_mock.status, LeagueStatus.CANCELLED)
        mock_dm.assert_called_once_with([555], unittest.mock.ANY)
        mock_announce.assert_called_once()

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.count_league_clubs")
    @patch("app.services.league_service.get_draft_league_by_guild")
    async def test_update_configuration_edit_guard(self, mock_get_draft, mock_count, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.target_club_count = 8
        league_mock.max_clubs = 8
        mock_get_draft.return_value = league_mock
        
        mock_count.return_value = 10 # 10 joined clubs
        
        # Attempt to lower target_club_count below joined count (10)
        res = await update_league_configuration("123", target_club_count=8)
        self.assertFalse(res.success)
        self.assertEqual(res.code, "invalid_target_club_count")
