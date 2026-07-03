# tests/test_manager_progression.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.models.manager import Manager
from app.models.club import Club
from app.models.facility import Facility, FacilityType, FacilityStatus
from app.models.fixture import Fixture, FixtureStatus
from app.models.manager_xp_event import ManagerXPEvent
from app.services.manager_progress_service import ManagerProgressService, ManagerProgressDTO
from app.services.facility_service import FacilityService
from app.services.matchday_service import MatchdayService
from app.config import config

class TestManagerProgression(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.manager_id = uuid.uuid4()
        self.guild_id = "123456789"
        self.club_id = uuid.uuid4()
        
        self.manager = Manager(
            id=self.manager_id,
            guild_id=self.guild_id,
            discord_user_id="987654321",
            club_id=self.club_id,
            career_xp=0,
            coins=1000
        )
        
        self.club = Club(
            id=self.club_id,
            guild_id=self.guild_id,
            manager_id=self.manager_id,
            name="Test United",
            normalized_name="test united",
            budget=1000000,
            stadium_capacity=10000
        )

    def test_manager_career_xp_defaults_to_zero(self):
        m = Manager(guild_id="123", discord_user_id="456")
        self.assertEqual(m.career_xp, 0)

    def test_manager_level_calculated_from_threshold_table(self):
        # Level 1: 0 XP
        self.assertEqual(ManagerProgressService.calculate_level(0), 1)
        self.assertEqual(ManagerProgressService.calculate_level(50), 1)
        # Level 2: 100 XP
        self.assertEqual(ManagerProgressService.calculate_level(100), 2)
        self.assertEqual(ManagerProgressService.calculate_level(239), 2)
        # Level 3: 240 XP
        self.assertEqual(ManagerProgressService.calculate_level(240), 3)
        # Level 36: 32580 XP
        self.assertEqual(ManagerProgressService.calculate_level(32580), 36)
        self.assertEqual(ManagerProgressService.calculate_level(50000), 36)

    def test_manager_level_dto_progress_calculation(self):
        # Test progress at 120 XP (Level 2: range 100 to 240, progress within level = 20/140 = 14.3%)
        dto = ManagerProgressService.calculate_progress(120)
        self.assertEqual(dto.manager_level, 2)
        self.assertEqual(dto.current_level_xp, 100)
        self.assertEqual(dto.next_level_xp, 240)
        self.assertEqual(dto.xp_into_level, 20)
        self.assertEqual(dto.xp_needed_for_next_level, 120)
        self.assertEqual(dto.progress_percent, 14.3)

        # Test max level progress (35000 XP)
        dto_max = ManagerProgressService.calculate_progress(35000)
        self.assertEqual(dto_max.manager_level, 36)
        self.assertIsNone(dto_max.next_level_xp)
        self.assertEqual(dto_max.progress_percent, 100.0)

    @patch("app.services.manager_progress_service.insert_xp_event_if_new")
    @patch("app.services.manager_progress_service.add_career_xp")
    async def test_xp_event_insert_awards_xp_once(self, mock_add_xp, mock_insert):
        session_mock = AsyncMock()
        mock_insert.return_value = True
        
        awarded = await ManagerProgressService.award_xp(
            session=session_mock,
            manager_id=self.manager_id,
            guild_id=self.guild_id,
            source_type="test_event",
            source_id="source_1",
            xp_amount=50
        )
        
        self.assertTrue(awarded)
        mock_insert.assert_called_once()
        mock_add_xp.assert_called_once_with(session_mock, self.manager_id, 50)

    @patch("app.services.manager_progress_service.insert_xp_event_if_new")
    @patch("app.services.manager_progress_service.add_career_xp")
    async def test_duplicate_xp_event_does_not_increment_xp(self, mock_add_xp, mock_insert):
        session_mock = AsyncMock()
        mock_insert.return_value = False
        
        awarded = await ManagerProgressService.award_xp(
            session=session_mock,
            manager_id=self.manager_id,
            guild_id=self.guild_id,
            source_type="test_event",
            source_id="source_1",
            xp_amount=50
        )
        
        self.assertFalse(awarded)
        mock_insert.assert_called_once()
        mock_add_xp.assert_not_called()

    @patch("app.services.manager_progress_service.ManagerProgressService.award_xp")
    async def test_league_fixture_played_awards_xp_and_bonuses(self, mock_award_xp):
        session_mock = AsyncMock()
        fixture = Fixture(id=uuid.uuid4(), guild_id=self.guild_id, status=FixtureStatus.PLAYED)
        
        home_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), name="Home FC", is_bot_controlled=False)
        away_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), name="Away FC", is_bot_controlled=False)
        
        # Sim result: Home victory 3-0
        sim_result = MagicMock()
        sim_result.home_goals = 3
        sim_result.away_goals = 0
        
        await ManagerProgressService.award_league_fixture_xp(
            session=session_mock,
            fixture=fixture,
            home_club=home_club,
            away_club=away_club,
            sim_result=sim_result
        )
        
        # Check awards for Home manager (Played, Win, Clean Sheet, Scored 3+)
        # Check awards for Away manager (Played, Loss)
        # Expected calls for home: played, win, clean_sheet, scored_3_plus
        # Expected calls for away: played, loss
        self.assertEqual(mock_award_xp.call_count, 6)
        
        # Verify first call is Home Played
        mock_award_xp.assert_any_call(
            session=session_mock,
            manager_id=home_club.manager_id,
            guild_id=self.guild_id,
            source_type="league_fixture_played",
            source_id=f"{fixture.id}:{home_club.id}",
            xp_amount=config.MANAGER_XP_LEAGUE_PLAYED,
            description=f"League Matchday Played: {home_club.name} vs {away_club.name}"
        )
        # Verify win
        mock_award_xp.assert_any_call(
            session=session_mock,
            manager_id=home_club.manager_id,
            guild_id=self.guild_id,
            source_type="league_fixture_win",
            source_id=f"{fixture.id}:{home_club.id}",
            xp_amount=config.MANAGER_XP_LEAGUE_WIN,
            description=f"League Victory: {home_club.name} 3–0 {away_club.name}"
        )

    @patch("app.services.manager_progress_service.ManagerProgressService.award_xp")
    async def test_bot_club_gets_no_manager_xp(self, mock_award_xp):
        session_mock = AsyncMock()
        fixture = Fixture(id=uuid.uuid4(), guild_id=self.guild_id, status=FixtureStatus.PLAYED)
        
        home_club = Club(id=uuid.uuid4(), manager_id=None, name="Bot FC", is_bot_controlled=True)
        away_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), name="Away FC", is_bot_controlled=False)
        
        sim_result = MagicMock()
        sim_result.home_goals = 1
        sim_result.away_goals = 1
        
        await ManagerProgressService.award_league_fixture_xp(
            session=session_mock,
            fixture=fixture,
            home_club=home_club,
            away_club=away_club,
            sim_result=sim_result
        )
        
        # Only away manager (non-bot) should get awards (played + draw)
        self.assertEqual(mock_award_xp.call_count, 2)

    @patch("app.services.manager_progress_service.ManagerProgressService.award_xp")
    async def test_friendly_match_awards_zero_xp(self, mock_award_xp):
        session_mock = AsyncMock()
        # Friendly fixture is handled in friendly_service.py which does not call award_league_fixture_xp,
        # but let's test that award_league_fixture_xp ignores non-played fixtures
        fixture = Fixture(id=uuid.uuid4(), status=FixtureStatus.SCHEDULED)
        
        home_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), is_bot_controlled=False)
        away_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), is_bot_controlled=False)
        
        sim_result = MagicMock()
        
        await ManagerProgressService.award_league_fixture_xp(
            session=session_mock,
            fixture=fixture,
            home_club=home_club,
            away_club=away_club,
            sim_result=sim_result
        )
        
        mock_award_xp.assert_not_called()

    async def test_facility_upgrade_blocked_when_manager_level_too_low(self):
        session_mock = AsyncMock()
        # Facility is already Lv.2 — upgrading to Lv.3 requires Manager Level 4.
        # Manager has 0 XP (Level 1), so this should be blocked.
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.STADIUM, level=2, status=FacilityStatus.IDLE)

        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "managers" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.manager
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = None
            return mock_res

        session_mock.execute.side_effect = exec_side_effect

        with self.assertRaises(ValueError) as context:
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.STADIUM)

        self.assertIn("requires Manager Level 4", str(context.exception))

        # Verify budget was NOT deducted (original is 1,000,000)
        self.assertEqual(self.club.budget, 1000000)
        self.assertEqual(fac.status, FacilityStatus.IDLE)

    async def test_facility_upgrade_allowed_when_manager_level_met(self):
        session_mock = AsyncMock()
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.STADIUM, level=1, status=FacilityStatus.IDLE)
        
        # Manager is Level 1 (0 XP). Facility Lv.2 now requires Manager Level 1 (Option A).
        # So the upgrade should be ALLOWED immediately for new managers.
        
        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "managers" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.manager
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = None
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        
        updated_fac = await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.STADIUM)
        
        self.assertEqual(updated_fac.status, FacilityStatus.UPGRADING)
        # Cost for level 1 facility is 250,000 (V1.1 config).
        # Budget should be deducted: 1,000,000 - 250,000 = 750,000.
        self.assertEqual(self.club.budget, 750000)

    @patch("app.services.club_service.get_manager_by_discord_id")
    @patch("app.services.club_service.get_club_by_manager_id")
    @patch("app.services.club_service.get_players_by_club_id")
    @patch("app.services.facility_service.FacilityService.ensure_default_facilities")
    async def test_club_dashboard_summary_contains_manager_progress(
        self, mock_ensure_fac, mock_get_players, mock_get_club, mock_get_manager
    ):
        # We patch the database calls inside get_manager_club_summary
        mock_get_manager.return_value = self.manager
        mock_get_club.return_value = self.club
        mock_get_players.return_value = []
        
        mock_ensure_fac.return_value = []
        
        from app.services.club_service import get_manager_club_summary
        summary = await get_manager_club_summary(self.guild_id, "987654321")
        
        self.assertIsNotNone(summary)
        self.assertIn("manager_progress", summary)
        self.assertEqual(summary["manager_progress"]["manager_level"], 1)
        self.assertEqual(summary["manager_progress"]["career_xp"], 0)

    async def test_facility_upgrade_checks_level_before_budget(self):
        session_mock = AsyncMock()
        # Facility is Lv.2 — upgrading to Lv.3 requires Manager Level 4.
        # Budget is also too low. Level check must fire FIRST (not budget error).
        fac = Facility(club_id=self.club_id, facility_type=FacilityType.STADIUM, level=2, status=FacilityStatus.IDLE)

        self.club.budget = 500  # Less than 750,000 Lv.2→3 cost AND level is too low

        async def exec_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "clubs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.club
            elif "managers" in stmt_str:
                mock_res.scalar_one_or_none.return_value = self.manager
            elif "facilities" in stmt_str:
                if "for update" in stmt_str:
                    mock_res.scalar_one_or_none.return_value = fac
                else:
                    mock_res.scalars.return_value.first.return_value = None
            return mock_res

        session_mock.execute.side_effect = exec_side_effect

        with self.assertRaises(ValueError) as context:
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.STADIUM)

        self.assertIn("requires Manager Level 4", str(context.exception))

    @patch("app.services.manager_progress_service.ManagerProgressService.award_xp")
    async def test_consequence_already_applied_still_allows_missing_xp_award(self, mock_award_xp):
        # Even if consequences were already applied, matchday retry runs and award_league_fixture_xp should still execute.
        session_mock = AsyncMock()
        fixture = Fixture(id=uuid.uuid4(), guild_id=self.guild_id, status=FixtureStatus.PLAYED)
        
        home_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), is_bot_controlled=False)
        away_club = Club(id=uuid.uuid4(), manager_id=uuid.uuid4(), is_bot_controlled=False)
        
        sim_result = MagicMock()
        sim_result.home_goals = 1
        sim_result.away_goals = 1
        
        # Calling XP awarding should succeed and attempt to award XP (2 for home, 2 for away due to play + draw)
        await ManagerProgressService.award_league_fixture_xp(
            session=session_mock,
            fixture=fixture,
            home_club=home_club,
            away_club=away_club,
            sim_result=sim_result
        )
        self.assertEqual(mock_award_xp.call_count, 4)

    @patch("app.services.manager_progress_service.insert_xp_event_if_new")
    @patch("app.services.manager_progress_service.add_career_xp")
    async def test_partial_xp_award_retry_awards_only_missing_events(self, mock_add_xp, mock_insert):
        # Scenario: played XP event already exists (mock_insert returns False).
        # win XP event is new (mock_insert returns True).
        # Only win XP should be added, played XP is not duplicated.
        session_mock = AsyncMock()
        
        # First call (played) is duplicate, second (win) is new
        mock_insert.side_effect = [False, True]
        
        fixture = Fixture(id=uuid.uuid4(), guild_id=self.guild_id, status=FixtureStatus.PLAYED)
        home_club = Club(id=uuid.uuid4(), manager_id=self.manager_id, is_bot_controlled=False)
        away_club = Club(id=uuid.uuid4(), manager_id=None, is_bot_controlled=True)  # Bot club ignored
        
        sim_result = MagicMock()
        sim_result.home_goals = 2
        sim_result.away_goals = 1
        
        await ManagerProgressService.award_league_fixture_xp(
            session=session_mock,
            fixture=fixture,
            home_club=home_club,
            away_club=away_club,
            sim_result=sim_result
        )
        
        # Verify insert was called for both events (played and win)
        self.assertEqual(mock_insert.call_count, 2)
        # Verify add_career_xp was only called ONCE (for the win XP event)
        mock_add_xp.assert_called_once_with(session_mock, self.manager_id, config.MANAGER_XP_LEAGUE_WIN)

    # --- Manager XP Balance Guardrails (V1.1) ---
    # These tests lock in the V1.1 XP ratios and level-gate policy.
    # If XP is re-inflated, level thresholds are changed, or gate policy shifts,
    # these will fail first — before it causes balance regressions in production.

    def test_loss_manager_xp_is_not_zero(self):
        """
        A loss should still award some XP (played + loss bonus).
        Managers must always feel progress, even in a bad run.
        """
        loss_xp = config.MANAGER_XP_LEAGUE_PLAYED + config.MANAGER_XP_LEAGUE_LOSS
        self.assertGreater(loss_xp, 0,
            msg="A league loss must still award positive Manager XP.")

    def test_big_win_manager_xp_is_below_100(self):
        """
        The best possible single match (win + clean sheet + 3 goals) must stay below 100 XP.
        Keeping the max low prevents level-jumping in short bursts.
        """
        max_xp = (
            config.MANAGER_XP_LEAGUE_PLAYED
            + config.MANAGER_XP_LEAGUE_WIN
            + config.MANAGER_XP_CLEAN_SHEET
            + config.MANAGER_XP_SCORED_3_PLUS
        )
        self.assertLess(max_xp, 100,
            msg=f"Best-case match XP is {max_xp}. Should be < 100 to prevent rapid level-jumping.")

    def test_manager_level_4_requires_multiple_matches(self):
        """
        Manager Level 4 should require at least 5 matches of average play.
        Average XP per match ≈ 45–55 XP (draw result).
        """
        level_4_threshold = config.MANAGER_LEVEL_XP_THRESHOLDS[4]
        avg_xp_per_match = config.MANAGER_XP_LEAGUE_PLAYED + config.MANAGER_XP_LEAGUE_DRAW
        matches_needed = level_4_threshold / avg_xp_per_match
        self.assertGreaterEqual(matches_needed, 5,
            msg=(
                f"Manager Level 4 at {level_4_threshold} XP only takes {matches_needed:.1f} "
                f"average matches. Should require >= 5."
            ))

    def test_manager_level_7_requires_long_term_play(self):
        """
        Manager Level 7 must require at least 15 average matches.
        This is the Lv.3→4 facility gate tier.
        """
        level_7_threshold = config.MANAGER_LEVEL_XP_THRESHOLDS[7]
        avg_xp_per_match = config.MANAGER_XP_LEAGUE_PLAYED + config.MANAGER_XP_LEAGUE_WIN
        matches_needed = level_7_threshold / avg_xp_per_match
        self.assertGreaterEqual(matches_needed, 15,
            msg=(
                f"Manager Level 7 at {level_7_threshold} XP only takes {matches_needed:.1f} "
                f"win matches. Should require >= 15."
            ))

    def test_manager_level_10_aligns_with_late_facility_upgrade(self):
        """
        Manager Level 10 must require at least 35 average matches.
        This gates the Lv.4→5 facility tier (54 matches budget target).
        """
        level_10_threshold = config.MANAGER_LEVEL_XP_THRESHOLDS[10]
        avg_xp_per_match = config.MANAGER_XP_LEAGUE_PLAYED + config.MANAGER_XP_LEAGUE_WIN
        matches_needed = level_10_threshold / avg_xp_per_match
        self.assertGreaterEqual(matches_needed, 35,
            msg=(
                f"Manager Level 10 at {level_10_threshold} XP only takes {matches_needed:.1f} "
                f"win matches. Should require >= 35."
            ))

    def test_facility_level_2_requires_manager_level_1(self):
        """
        Option A: Facility Lv.2 upgrade must be immediately available to Level 1 managers.
        New users should be able to make one immediate strategic facility choice.
        """
        lv2_gate = config.FACILITY_MANAGER_LEVEL_REQUIREMENTS.get(2)
        self.assertEqual(lv2_gate, 1,
            msg=(
                f"Facility Lv.2 gate is Manager Level {lv2_gate}. "
                f"Option A requires it to be Level 1 for onboarding."
            ))

    def test_facility_level_3_requires_manager_level_4(self):
        """
        Facility Lv.3 upgrade must require Manager Level 4.
        This is the first real gate — ensures managers play ~8 matches before second tier.
        """
        lv3_gate = config.FACILITY_MANAGER_LEVEL_REQUIREMENTS.get(3)
        self.assertEqual(lv3_gate, 4,
            msg=f"Facility Lv.3 gate is Manager Level {lv3_gate}. Expected Level 4.")

    def test_xp_win_greater_than_draw_greater_than_loss(self):
        """
        XP rewards must reflect result quality: win > draw > loss.
        Flattening these removes the incentive to play for results.
        """
        self.assertGreater(
            config.MANAGER_XP_LEAGUE_WIN,
            config.MANAGER_XP_LEAGUE_DRAW,
            msg="Win XP must be greater than draw XP."
        )
        self.assertGreater(
            config.MANAGER_XP_LEAGUE_DRAW,
            config.MANAGER_XP_LEAGUE_LOSS,
            msg="Draw XP must be greater than loss XP."
        )
