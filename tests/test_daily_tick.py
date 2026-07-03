# tests/test_daily_tick.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.player import Player
from app.models.daily_tick_runs import DailyTickRun, DailyTickRunStatus
from app.models.guild_config import GuildConfig
from app.services.daily_tick_service import DailyTickService
from app.config import config

class TestDailyTick(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Default mock guild configuration
        self.guild_id = 123456789
        self.guild_config = GuildConfig(
            guild_id=str(self.guild_id),
            matchday_timezone="Asia/Kathmandu"
        )
        self.now_utc = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_runs_once_per_guild_per_day(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        # Existing successful run today
        local_tz = ZoneInfo(self.guild_config.matchday_timezone)
        local_date = self.now_utc.astimezone(local_tz).date()
        
        existing_run = DailyTickRun(
            guild_id=str(self.guild_id),
            tick_date=local_date,
            status=DailyTickRunStatus.SUCCESS,
            started_at=self.now_utc - timedelta(hours=1),
            finished_at=self.now_utc - timedelta(minutes=50)
        )
        
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = existing_run
        session_mock.execute.return_value = mock_execute
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNone(result)
        # Players query should not have been run
        session_mock.execute.assert_called_once()  # only checked for daily tick run

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_recovers_non_injured_players(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        # Mock players
        p1 = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="P1",
            fitness=85,
            injury_days_remaining=0,
            is_retired=False
        )
        p2 = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="P2",
            fitness=95,
            injury_days_remaining=0,
            is_retired=False
        )
        
        async def session_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "daily_tick_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = None
            elif "<=" in stmt_str:
                mock_res.scalars.return_value.all.return_value = []
            elif "players" in stmt_str:
                mock_res.scalars.return_value.all.return_value = [p1, p2]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.status, DailyTickRunStatus.SUCCESS)
        
        # Fitness recovery checked (default recovery = 10)
        self.assertEqual(p1.fitness, 95)
        # Capped at 100
        self.assertEqual(p2.fitness, 100)

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_recovers_injured_players_more_slowly(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        # Injured player (created yesterday)
        yesterday_utc = self.now_utc - timedelta(days=1)
        p = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="Injured Player",
            fitness=70,
            injury_type="Hamstring Pull",
            injury_severity="strain",
            injury_days_remaining=3,
            injury_created_at=yesterday_utc,
            is_retired=False
        )
        
        async def session_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "daily_tick_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = None
            elif "<=" in stmt_str:
                mock_res.scalars.return_value.all.return_value = []
            elif "players" in stmt_str:
                mock_res.scalars.return_value.all.return_value = [p]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNotNone(result)
        # Injured recovery rate (default recovery = 5)
        self.assertEqual(p.fitness, 75)
        # Days remaining decremented by 1
        self.assertEqual(p.injury_days_remaining, 2)
        # Fields not cleared yet since days remaining > 0
        self.assertEqual(p.injury_severity, "strain")

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_does_not_reduce_new_same_day_injury(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        # Injured player (created today)
        p = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="New Injured Player",
            fitness=70,
            injury_type="Hamstring Pull",
            injury_severity="strain",
            injury_days_remaining=3,
            injury_created_at=self.now_utc,  # Same day
            is_retired=False
        )
        
        async def session_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "daily_tick_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = None
            elif "<=" in stmt_str:
                mock_res.scalars.return_value.all.return_value = []
            elif "players" in stmt_str:
                mock_res.scalars.return_value.all.return_value = [p]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNotNone(result)
        # Fitness still recovers slower
        self.assertEqual(p.fitness, 75)
        # Days remaining NOT decremented because it is same-day
        self.assertEqual(p.injury_days_remaining, 3)

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_clears_injury_when_days_reach_zero(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        # Injured player with 1 day remaining (created yesterday)
        yesterday_utc = self.now_utc - timedelta(days=1)
        p1 = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="Recovering Player Low Fit",
            fitness=40,  # Recovers to 45, then baseline 80
            injury_type="Hamstring Pull",
            injury_severity="strain",
            injury_days_remaining=1,
            injury_created_at=yesterday_utc,
            is_retired=False
        )
        p2 = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="Recovering Player High Fit",
            fitness=85,  # Recovers to 90, keeps 90 (max(90, 80) is 90)
            injury_type="Sprain",
            injury_severity="sprain",
            injury_days_remaining=1,
            injury_created_at=yesterday_utc,
            is_retired=False
        )
        
        async def session_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "daily_tick_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = None
            elif "<=" in stmt_str:
                mock_res.scalars.return_value.all.return_value = []
            elif "players" in stmt_str:
                mock_res.scalars.return_value.all.return_value = [p1, p2]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNotNone(result)
        
        # P1 recovered
        self.assertEqual(p1.injury_days_remaining, 0)
        self.assertIsNone(p1.injury_type)
        self.assertIsNone(p1.injury_severity)
        self.assertIsNone(p1.injury_created_at)
        self.assertEqual(p1.fitness, 80)  # Max(45, 80)
        
        # P2 recovered
        self.assertEqual(p2.injury_days_remaining, 0)
        self.assertIsNone(p2.injury_type)
        self.assertIsNone(p2.injury_severity)
        self.assertIsNone(p2.injury_created_at)
        self.assertEqual(p2.fitness, 90)  # Max(90, 80)

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_failed_run_can_retry(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        local_tz = ZoneInfo(self.guild_config.matchday_timezone)
        local_date = self.now_utc.astimezone(local_tz).date()
        
        existing_run = DailyTickRun(
            guild_id=str(self.guild_id),
            tick_date=local_date,
            status=DailyTickRunStatus.FAILED,
            started_at=self.now_utc - timedelta(hours=1),
            finished_at=self.now_utc - timedelta(minutes=50),
            error="Previous exception"
        )
        
        p = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="P",
            fitness=85,
            injury_days_remaining=0,
            is_retired=False
        )
        
        async def session_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "daily_tick_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = existing_run
            elif "<=" in stmt_str:
                mock_res.scalars.return_value.all.return_value = []
            elif "players" in stmt_str:
                mock_res.scalars.return_value.all.return_value = [p]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.status, DailyTickRunStatus.SUCCESS)
        self.assertIsNone(result.error)
        self.assertEqual(p.fitness, 95)

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_stale_running_run_can_recover(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()
        
        local_tz = ZoneInfo(self.guild_config.matchday_timezone)
        local_date = self.now_utc.astimezone(local_tz).date()
        
        # Stale run started 45 minutes ago (older than 30 mins)
        existing_run = DailyTickRun(
            guild_id=str(self.guild_id),
            tick_date=local_date,
            status=DailyTickRunStatus.RUNNING,
            started_at=self.now_utc - timedelta(minutes=45)
        )
        
        p = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            display_name="P",
            fitness=85,
            injury_days_remaining=0,
            is_retired=False
        )
        
        async def session_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "daily_tick_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = existing_run
            elif "<=" in stmt_str:
                mock_res.scalars.return_value.all.return_value = []
            elif "players" in stmt_str:
                mock_res.scalars.return_value.all.return_value = [p]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )
        
        self.assertIsNotNone(result)
        # Should finish successfully
        self.assertEqual(result.status, DailyTickRunStatus.SUCCESS)
        self.assertIsNone(result.error)
        self.assertEqual(p.fitness, 95)

if __name__ == "__main__":
    unittest.main()
