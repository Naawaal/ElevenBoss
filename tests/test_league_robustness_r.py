# tests/test_league_robustness_r.py

import unittest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.club import Club
from app.models.fixture import Fixture
from app.models.scheduler_run import SchedulerRun, SchedulerRunStatus
from app.repositories.scheduler_run_repository import get_or_create_running_job
from app.services.league_service import start_league, advance_season
from app.services.league_lifecycle_service import LeagueLifecycleService
from app.services.matchday_service import MatchdayService, MatchdayRunResult
from app.models.guild_config import GuildConfig


class TestLeagueRobustnessR(unittest.IsolatedAsyncioTestCase):

    @patch("app.repositories.scheduler_run_repository.select")
    async def test_get_or_create_running_job_new_and_failed(self, mock_select):
        """Test that get_or_create_running_job inserts new jobs and recycles failed jobs."""
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        session_mock.add_all = MagicMock()
        
        # Scenario 1: Job does not exist -> Creates new
        mock_result_empty = MagicMock()
        mock_result_empty.scalar_one_or_none.return_value = None
        session_mock.execute.return_value = mock_result_empty
        
        job = await get_or_create_running_job(
            session=session_mock,
            job_key="test_job_1",
            job_type="test",
            guild_id="123"
        )
        self.assertEqual(job.status, SchedulerRunStatus.RUNNING)
        self.assertEqual(job.job_key, "test_job_1")
        session_mock.add.assert_called_once()
        
        # Scenario 2: Job exists and is FAILED -> Resets to RUNNING
        session_mock.add.reset_mock()
        failed_job = SchedulerRun(
            job_key="test_job_1",
            job_type="test",
            status=SchedulerRunStatus.FAILED,
            error="Old error",
            finished_at=datetime.utcnow()
        )
        mock_result_failed = MagicMock()
        mock_result_failed.scalar_one_or_none.return_value = failed_job
        session_mock.execute.return_value = mock_result_failed
        
        recycled_job = await get_or_create_running_job(
            session=session_mock,
            job_key="test_job_1",
            job_type="test",
            guild_id="123"
        )
        self.assertEqual(recycled_job.status, SchedulerRunStatus.RUNNING)
        self.assertIsNone(recycled_job.error)
        self.assertIsNone(recycled_job.finished_at)
        session_mock.add.assert_not_called()  # Resets existing, no new insert

    @patch("app.services.league_service.get_session")
    @patch("app.services.league_service.claim_league_for_starting")
    @patch("app.services.league_service.get_active_league_by_guild")
    @patch("app.services.league_service.get_or_create_running_job")
    @patch("app.services.league_service.mark_job_success")
    async def test_league_start_retry_after_failed_attempt(
        self, mock_mark_success, mock_get_or_create_job, mock_active_league, mock_claim_league, mock_get_session
    ):
        """Test that start_league can be retried successfully after a failed start attempt."""
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        session_mock.add_all = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock

        league_mock = MagicMock()
        league_mock.id = uuid.uuid4()
        league_mock.name = "Test League"
        league_mock.target_club_count = 8
        league_mock.fill_bots_after_deadline = True
        league_mock.minimum_human_clubs = 2
        league_mock.status = LeagueStatus.DRAFT
        mock_claim_league.return_value = league_mock
        mock_active_league.return_value = None

        # Simulate 1st attempt: 10 human clubs (exceeds target count of 8) -> raises ValueError in validation
        human_clubs = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(10)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = human_clubs
        session_mock.execute.return_value = result_mock

        # First run fails validation due to joined clubs exceeding limit
        res = await start_league("123")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "database_error")
        # Lock is created, but transaction rolls back.
        mock_get_or_create_job.assert_called_once()
        mock_mark_success.assert_not_called()

        # Simulate 2nd attempt: Admin fixes to 6 humans
        mock_get_or_create_job.reset_mock()
        human_clubs_retry = [MagicMock(id=uuid.uuid4(), is_bot_controlled=False) for _ in range(6)]
        result_mock_retry = MagicMock()
        result_mock_retry.scalars.return_value.all.return_value = human_clubs_retry
        session_mock.execute.return_value = result_mock_retry
        
        # Stub the rest of the success path
        with patch("app.services.league_service.create_season") as mock_create_season, \
             patch("app.services.league_service.generate_bot_clubs_for_league") as mock_gen_bots, \
             patch("app.services.league_service.initialize_standings") as mock_init_standings, \
             patch("app.services.league_service.bulk_create_fixtures") as mock_bulk:
            
            mock_create_season.return_value = MagicMock(id=uuid.uuid4())
            mock_gen_bots.return_value = []
            
            res_retry = await start_league("123")
            self.assertTrue(res_retry.success)
            mock_get_or_create_job.assert_called_once()  # Reuses failed/stopped job
            mock_mark_success.assert_called_once()       # Finalizes successfully

    @patch("app.repositories.guild_config_repository.get_or_create_guild_config")
    @patch("app.repositories.get_or_create_running_job")
    @patch("app.repositories.mark_job_success")
    @patch("app.services.player_service.PlayerService.age_players")
    async def test_season_complete_auto_disabled_no_dangling_lock(
        self, mock_age_players, mock_mark_success, mock_get_or_create_job, mock_get_config
    ):
        """Test that completing a season with auto_start disabled transitions the season and finalizes the lock."""
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        session_mock.add_all = MagicMock()
        
        # Mock Season & League
        season = Season(id=uuid.uuid4(), league_id=uuid.uuid4(), status=SeasonStatus.ACTIVE, season_number=1)
        league = League(id=season.league_id, status=LeagueStatus.ACTIVE)
        
        # Set config auto_start_league to False
        config = GuildConfig(guild_id="123", auto_start_league=False)
        mock_get_config.return_value = config
        
        # Setup session queries to return season and league
        season_result = MagicMock()
        season_result.scalar_one_or_none.return_value = season
        
        league_result = MagicMock()
        league_result.scalar_one_or_none.return_value = league
        
        session_mock.execute.side_effect = [season_result, league_result]
        
        res = await LeagueLifecycleService.complete_current_season(session_mock, "123", season.id)
        
        self.assertTrue(res)
        self.assertEqual(season.status, SeasonStatus.COMPLETED)
        self.assertEqual(league.status, LeagueStatus.COMPLETED)
        mock_get_or_create_job.assert_called_once_with(
            session=session_mock,
            job_key=f"season_advance:123:{season.id}",
            job_type="season_advance",
            guild_id="123"
        )
        # Lock must be finalized as SUCCESS unconditionally
        mock_mark_success.assert_called_once_with(session_mock, f"season_advance:123:{season.id}")

    @patch("app.services.league_service.get_session")
    @patch("app.repositories.guild_config_repository.get_or_create_guild_config")
    async def test_manual_advance_blocked_if_auto_start_enabled(self, mock_get_config, mock_get_session):
        """Test that manual /league advance is rejected immediately if auto_start_league is enabled."""
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        config = GuildConfig(guild_id="123", auto_start_league=True)
        mock_get_config.return_value = config
        
        res = await advance_season("123")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "automation_active")
        self.assertEqual(res.message, "Manual season advancement is disabled because automated league lifecycle is active.")
        # DB transactions should not fetch league or season rows because shielding rejected early
        self.assertEqual(session_mock.execute.call_count, 0)

    @patch("app.services.matchday_service.get_session")
    @patch("app.services.matchday_service.get_active_league_by_guild")
    @patch("app.services.matchday_service.get_active_season_for_league")
    @patch("app.services.matchday_service.get_job_by_key")
    @patch("app.services.matchday_service.create_running_job")
    @patch("app.services.matchday_service.get_current_week_fixtures_for_update")
    @patch("app.services.matchday_service.get_clubs_in_league")
    @patch("app.services.lineup_service.get_players_by_club_id")
    @patch("app.services.player_service.PlayerService.get_available_players")
    @patch("app.services.lineup_service.get_active_lineup")
    @patch("app.services.lineup_service.save_lineup_with_players")
    @patch("app.services.matchday_service.simulate_match")
    @patch("app.services.matchday_service.mark_fixture_played")
    @patch("app.services.matchday_service.get_standing_for_update")
    @patch("app.services.matchday_service.get_fixture_week_range")
    @patch("app.services.league_lifecycle_service.LeagueLifecycleService.complete_current_season")
    @patch("app.services.matchday_service.mark_job_success")
    async def test_matchday_simulation_refreshes_bot_lineups(
        self, mock_mark_success, mock_complete_season, mock_get_fixture_week_range, mock_get_standing, mock_mark_played, mock_simulate,
        mock_save_lineup, mock_get_active_lineup, mock_available_players, mock_get_players, mock_get_clubs, mock_fixtures, mock_create_job,
        mock_get_job_by_key, mock_season, mock_league, mock_get_session
    ):
        """Test that running matchday simulation automatically regenerates lineups for bot filler clubs."""
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        session_mock.add_all = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        # Setup mocks
        league = League(id=uuid.uuid4(), name="Test League", status=LeagueStatus.ACTIVE)
        mock_league.return_value = league
        
        season = Season(id=uuid.uuid4(), league_id=league.id, status=SeasonStatus.ACTIVE, current_week=1)
        mock_season.return_value = season
        
        # 1 Fixture (Home: Bot, Away: Bot)
        bot_home = Club(id=uuid.uuid4(), name="Bot FC 1", is_bot_controlled=True, guild_id="123")
        bot_away = Club(id=uuid.uuid4(), name="Bot FC 2", is_bot_controlled=True, guild_id="123")
        fixture = Fixture(id=uuid.uuid4(), home_club_id=bot_home.id, away_club_id=bot_away.id, week=1, status="scheduled")
        fixture.home_club = bot_home
        fixture.away_club = bot_away
        mock_fixtures.return_value = [fixture]
        
        mock_get_clubs.return_value = [bot_home, bot_away]
        
        # Mock players
        players = [MagicMock(id=uuid.uuid4(), position="GK" if i == 0 else "CB", overall=70, fitness=100, is_retired=False) for i in range(15)]
        mock_get_players.return_value = players
        mock_available_players.return_value = players
        
        # Mock simulator output
        mock_simulate.return_value = MagicMock(home_goals=1, away_goals=0, home_possession=50, away_possession=50, home_shots=5, away_shots=5, home_shots_on_target=3, away_shots_on_target=2, goals=[], cards=[], substitutions=[], motm_player_id=str(players[0].id))
        
        # Stub standings updates
        mock_get_standing.return_value = MagicMock()
        
        # Make get_job_by_key and get_active_lineup return None
        mock_get_job_by_key.return_value = None
        mock_get_active_lineup.return_value = None
        mock_get_fixture_week_range.return_value = (1, 2)
        mock_complete_season.return_value = True
        
        # Run matchday simulation
        with patch("app.services.matchday_service.get_players_by_club_id", return_value=players), \
             patch("app.services.matchday_service.save_lineup_with_players", mock_save_lineup), \
             patch("app.services.match_consequence_service.MatchConsequenceService.apply_league_match_consequences"):
            res = await MatchdayService.run_current_matchday("123", 999, is_admin=True)
        
        self.assertTrue(res.success)
        # Lineups should be auto-refreshed for both bot clubs + fallbacks
        self.assertEqual(mock_save_lineup.call_count, 4)
        # Verify first call is for bot_home or bot_away
        called_club_ids = {arg[0][2] for arg in mock_save_lineup.call_args_list}
        self.assertIn(bot_home.id, called_club_ids)
        self.assertIn(bot_away.id, called_club_ids)
