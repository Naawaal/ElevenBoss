# tests/test_facilities.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from datetime import datetime, timedelta, timezone
from app.models.club import Club
from app.models.facility import Facility, FacilityType, FacilityStatus
from app.models.player import Player
from app.models.daily_tick_runs import DailyTickRunStatus
from app.models.guild_config import GuildConfig
from app.services.facility_service import FacilityService
from app.services.daily_tick_service import DailyTickService
from app.config import config

class TestFacilities(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.guild_id = 123456789
        self.club_id = uuid.uuid4()
        self.club = Club(
            id=self.club_id,
            guild_id=str(self.guild_id),
            name="Test FC",
            normalized_name="test fc",
            budget=500000,
            stadium_capacity=10000
        )
        self.now_utc = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
        self.guild_config = GuildConfig(
            guild_id=str(self.guild_id),
            matchday_timezone="UTC"
        )

    async def test_get_or_create_facilities_creates_all_five(self):
        session_mock = AsyncMock()
        
        # When no facilities exist in DB, it returns empty list, and then creates them
        mock_execute = MagicMock()
        mock_execute.scalars.return_value.all.return_value = []
        session_mock.execute.return_value = mock_execute
        
        facilities = await FacilityService.ensure_default_facilities(session_mock, self.club_id)
        
        # Should have created 5 facilities
        self.assertEqual(len(facilities), 5)
        facilities_dict = {f.facility_type: f for f in facilities}
        for f_type in FacilityType:
            self.assertIn(f_type, facilities_dict)
            fac = facilities_dict[f_type]
            self.assertEqual(fac.level, 1)
            self.assertEqual(fac.status, FacilityStatus.IDLE)
            self.assertEqual(fac.club_id, self.club_id)

        # Verify add was called 5 times
        self.assertEqual(session_mock.add.call_count, 5)

    async def test_get_or_create_facilities_backfills_missing(self):
        session_mock = AsyncMock()
        
        # DB has stadium and training pitch but lacks the other three
        std = Facility(club_id=self.club_id, facility_type=FacilityType.STADIUM, level=2, status=FacilityStatus.IDLE)
        pt = Facility(club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.UPGRADING)
        
        mock_execute = MagicMock()
        mock_execute.scalars.return_value.all.return_value = [std, pt]
        session_mock.execute.return_value = mock_execute
        
        facilities = await FacilityService.ensure_default_facilities(session_mock, self.club_id)
        facilities_dict = {f.facility_type: f for f in facilities}
        
        # Verify stadium and pitch are preserved
        self.assertEqual(facilities_dict[FacilityType.STADIUM].level, 2)
        self.assertEqual(facilities_dict[FacilityType.TRAINING_PITCH].status, FacilityStatus.UPGRADING)
        
        # Verify the other three are created
        self.assertEqual(facilities_dict[FacilityType.YOUTH_ACADEMY].level, 1)
        self.assertEqual(facilities_dict[FacilityType.MEDICAL_CLINIC].level, 1)
        self.assertEqual(facilities_dict[FacilityType.CLUB_HQ].level, 1)
        
        # 3 missing facilities added
        self.assertEqual(session_mock.add.call_count, 3)

    async def test_start_upgrade_success(self):
        session_mock = AsyncMock()
        
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.IDLE)
        
        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "managers" in stmt_str:
                from app.models.manager import Manager
                mock_res.scalar_one_or_none.return_value = Manager(
                    guild_id=str(self.guild_id),
                    discord_user_id="123",
                    club_id=self.club_id,
                    career_xp=1000
                )
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = None
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        
        result_fac = await FacilityService.start_upgrade(
            session_mock,
            self.club_id,
            FacilityType.TRAINING_PITCH,
            now_utc=self.now_utc
        )
        
        self.assertEqual(result_fac.status, FacilityStatus.UPGRADING)
        self.assertEqual(result_fac.level, 1) # Still level 1 until completed
        self.assertIsNotNone(result_fac.upgrade_started_at)
        self.assertIsNotNone(result_fac.upgrade_completes_at)
        
        # Verify budget was debited
        cost = config.FACILITY_UPGRADE_COSTS[1]
        self.assertEqual(self.club.budget, 500000 - cost)

    async def test_start_upgrade_fails_if_insufficient_budget(self):
        session_mock = AsyncMock()
        self.club.budget = 100 # Very low budget
        
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.IDLE)
        
        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "managers" in stmt_str:
                from app.models.manager import Manager
                mock_res.scalar_one_or_none.return_value = Manager(
                    guild_id=str(self.guild_id),
                    discord_user_id="123",
                    club_id=self.club_id,
                    career_xp=1000
                )
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = None
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        
        with self.assertRaises(ValueError) as context:
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.TRAINING_PITCH, now_utc=self.now_utc)
        self.assertIn("Insufficient funds", str(context.exception))

    async def test_start_upgrade_fails_if_another_facility_upgrading(self):
        session_mock = AsyncMock()
        
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.IDLE)
        other_upgrading = Facility(club_id=self.club_id, facility_type=FacilityType.STADIUM, level=1, status=FacilityStatus.UPGRADING)
        
        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = other_upgrading
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        
        with self.assertRaises(ValueError) as context:
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.TRAINING_PITCH, now_utc=self.now_utc)
        self.assertIn("Only one upgrade can be active at a time", str(context.exception))

    async def test_start_upgrade_fails_if_already_max_level(self):
        session_mock = AsyncMock()
        
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=config.FACILITY_MAX_LEVEL, status=FacilityStatus.MAX_LEVEL)
        
        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = None
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        
        with self.assertRaises(ValueError) as context:
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.TRAINING_PITCH, now_utc=self.now_utc)
        self.assertIn("already at the maximum level", str(context.exception))

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_daily_tick_completes_pending_upgrades(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()

        # Mock a facility that finished upgrading (duration was 12h, upgrade completes 1h ago)
        std_fac = Facility(
            club_id=self.club_id,
            facility_type=FacilityType.STADIUM,
            level=1,
            status=FacilityStatus.UPGRADING,
            upgrade_started_at=self.now_utc - timedelta(hours=13),
            upgrade_completes_at=self.now_utc - timedelta(hours=1),
            club=self.club
        )

        run_executed = False
        async def exec_side_effect(stmt):
            nonlocal run_executed
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if not run_executed:
                mock_res.scalar_one_or_none.return_value = None
                run_executed = True
            else:
                if "<=" in stmt_str:
                    mock_res.scalars.return_value.all.return_value = [std_fac]
                elif "players" in stmt_str:
                    mock_res.scalars.return_value.all.return_value = []
                else:
                    mock_res.scalars.return_value.all.return_value = [std_fac]
            return mock_res

        session_mock.execute.side_effect = exec_side_effect

        result = await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, DailyTickRunStatus.SUCCESS)

        # Facility level should have incremented
        self.assertEqual(std_fac.level, 2)
        self.assertEqual(std_fac.status, FacilityStatus.IDLE)
        self.assertIsNone(std_fac.upgrade_completes_at)
        
        # Stadium capacity in club should have updated
        self.assertEqual(self.club.stadium_capacity, config.STADIUM_CAPACITY_BY_LEVEL[2])

    @patch("app.services.daily_tick_service.get_or_create_guild_config")
    async def test_facility_bonuses_applied_to_recovery(self, mock_get_config):
        mock_get_config.return_value = self.guild_config
        session_mock = AsyncMock()
        session_mock.add = MagicMock()

        # Stadium level 2, training pitch level 3, clinic level 2
        fac1 = Facility(club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=3, status=FacilityStatus.IDLE)
        fac2 = Facility(club_id=self.club_id, facility_type=FacilityType.MEDICAL_CLINIC, level=2, status=FacilityStatus.IDLE)

        # Players: p1 (healthy, fatigued), p2 (injured)
        yesterday_utc = self.now_utc - timedelta(days=1)
        p1 = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            club_id=self.club_id,
            display_name="Healthy Player",
            fitness=80,
            injury_days_remaining=0,
            is_retired=False
        )
        p2 = Player(
            id=uuid.uuid4(),
            guild_id=str(self.guild_id),
            club_id=self.club_id,
            display_name="Injured Player",
            fitness=60,
            injury_type="Strain",
            injury_severity="strain",
            injury_days_remaining=3,
            injury_created_at=yesterday_utc,
            is_retired=False
        )

        run_executed = False
        async def exec_side_effect(stmt):
            nonlocal run_executed
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if not run_executed:
                mock_res.scalar_one_or_none.return_value = None
                run_executed = True
            else:
                if "<=" in stmt_str:
                    mock_res.scalars.return_value.all.return_value = []
                elif "players" in stmt_str:
                    mock_res.scalars.return_value.all.return_value = [p1, p2]
                else:
                    mock_res.scalars.return_value.all.return_value = [fac1, fac2]
            return mock_res

        session_mock.execute.side_effect = exec_side_effect

        await DailyTickService.run_daily_tick(
            session=session_mock,
            guild_id=self.guild_id,
            now_utc=self.now_utc
        )

        # Healthy player recovery = base (10) + Training Pitch Lvl 3 bonus (2) = 12. Total 80 + 12 = 92
        self.assertEqual(p1.fitness, 92)

        # Injured player recovery = base (5) + Clinic Lvl 2 bonus (1) = 6. Total 60 + 6 = 66
        self.assertEqual(p2.fitness, 66)
