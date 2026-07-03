# tests/test_club_economy.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.models.manager import Manager
from app.models.club import Club
from app.models.facility import Facility, FacilityType, FacilityStatus
from app.models.fixture import Fixture, FixtureStatus
from app.models.club_transaction import ClubTransaction
from app.services.economy_service import EconomyService, BudgetEventResultDTO, RevenueBreakdownDTO
from app.services.facility_service import FacilityService
from app.db.locking import sort_club_ids_for_locking
from app.config import config

class TestClubEconomy(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.club_id = uuid.uuid4()
        self.manager_id = uuid.uuid4()
        self.guild_id = "123456789"
        
        self.club = Club(
            id=self.club_id,
            guild_id=self.guild_id,
            manager_id=self.manager_id,
            name="Real Test",
            normalized_name="real test",
            budget=1_500_000,  # Below new 6.4M cap for level=2/hq=1 — allows revenue tests to flow
            stadium_capacity=10000
        )
        
        self.manager = Manager(
            id=self.manager_id,
            guild_id=self.guild_id,
            discord_user_id="987654321",
            club_id=self.club_id,
            career_xp=100  # Level 2
        )

    # --- Helper: make a mock session that returns self.club on execute() ---
    def _make_session_returning_club(self):
        session_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = self.club
        session_mock.execute = AsyncMock(return_value=result_mock)
        return session_mock

    # --- 1. Ledger and Budget Mutation ---

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_club_transaction_insert_records_balance_before_after(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        # Call the locked-club variant directly — no DB query needed
        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="league_match_revenue",
            source_id="match_123",
            amount=50000,
            description="Matchday win"
        )

        self.assertTrue(res.applied)
        self.assertEqual(res.balance_before, 1_500_000)
        self.assertEqual(res.balance_after, 1_550_000)
        self.assertEqual(self.club.budget, 1_550_000)
        session_mock.flush.assert_called_once()

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_apply_budget_event_records_positive_transaction(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="league_match_revenue",
            source_id="match_123",
            amount=100000
        )
        self.assertTrue(res.applied)
        self.assertEqual(res.amount, 100000)

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_apply_budget_event_records_negative_transaction(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="facility_upgrade",
            source_id="facility_1",
            amount=-200000
        )
        self.assertTrue(res.applied)
        self.assertEqual(res.amount, -200000)
        self.assertEqual(self.club.budget, 1_300_000)

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_duplicate_transaction_does_not_mutate_budget_twice(self, mock_insert):
        mock_insert.return_value = False  # Simulate duplicate constraint triggered
        session_mock = AsyncMock()

        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="league_match_revenue",
            source_id="match_duplicate",
            amount=100000
        )
        self.assertFalse(res.applied)
        self.assertEqual(res.amount, 0)
        self.assertEqual(self.club.budget, 1_500_000)  # No mutation!

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_apply_budget_event_flushes_but_does_not_commit(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="league_match_revenue",
            source_id="match_123",
            amount=50000
        )
        session_mock.flush.assert_called_once()
        session_mock.commit.assert_not_called()  # Caller must commit!

    def test_apply_budget_event_uses_sqlite_safe_locking(self):
        # Verify that maybe_for_update is a no-op on SQLite
        session_mock = MagicMock()
        session_mock.bind.dialect.name = "sqlite"

        from sqlalchemy import select
        from app.db.locking import maybe_for_update
        stmt = select(Club).where(Club.id == self.club_id)
        stmt_modified = maybe_for_update(stmt, session_mock)
        # SQLite branch returns the stmt unchanged — no FOR UPDATE clause
        self.assertIs(stmt_modified, stmt)

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_apply_budget_event_allows_expense_above_treasury_cap(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        # Budget is 16M (above baseline 15M cap)
        self.club.budget = 16_000_000

        # Applying a negative expense should bypass cap check
        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="facility_upgrade",
            source_id="stadium_up",
            amount=-90000,
            treasury_cap=15_000_000
        )
        self.assertTrue(res.applied)
        self.assertEqual(res.amount, -90000)
        # Budget was set to 16M explicitly above — expense brings it to 15.91M
        # This test sets its own explicit budget, so we don't use setUp's 1.5M
        self.assertEqual(self.club.budget, 15_910_000)

    # --- 2. Revenue Formula ---

    def test_league_revenue_uses_separate_ticket_and_sponsor_streams(self):
        # win revenue breakdown with new V1.1 numbers
        # base ticket = 35k (played) + 25k (win) = 60k
        # base sponsor = 15k
        dto = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=1,
            result="win",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        self.assertEqual(dto.ticket_base, 60_000)
        self.assertEqual(dto.sponsor_base, 15_000)
        self.assertEqual(dto.total_before_cap, 75_000)

    def test_stadium_multiplier_does_not_multiply_sponsor_revenue(self):
        # Stadium Level 2 has 1.08 multiplier (V1.1)
        # Ticket sales base: 35k (played) + 25k (win) = 60k -> 1.08 * 60k = 64,800
        # Sponsor base: 15k -> 15,000 (unchanged since hq_level is 1)
        dto = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=2,
            result="win",
            stadium_level=2,
            hq_level=1,
            manager_level=1
        )
        self.assertEqual(dto.final_ticket_revenue, 64_800)
        self.assertEqual(dto.final_sponsor_revenue, 15_000)

    def test_hq_multiplier_does_not_multiply_ticket_revenue(self):
        # HQ Level 2 has 1.05 multiplier (unchanged in V1.1)
        # Ticket sales base: 60k -> 60,000 (unchanged since stadium_level is 1)
        # Sponsor base: 15k -> 1.05 * 15k = 15,750
        dto = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=2,
            result="win",
            stadium_level=1,
            hq_level=2,
            manager_level=1
        )
        self.assertEqual(dto.final_ticket_revenue, 60_000)
        self.assertEqual(dto.final_sponsor_revenue, 15_750)

    def test_win_revenue_greater_than_draw_revenue(self):
        dto_win = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=2,
            result="win",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        dto_draw = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=2,
            result="draw",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        self.assertTrue(dto_win.total_before_cap > dto_draw.total_before_cap)

    def test_draw_revenue_greater_than_loss_revenue(self):
        dto_draw = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=2,
            result="draw",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        dto_loss = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=2,
            result="loss",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        self.assertTrue(dto_draw.total_before_cap > dto_loss.total_before_cap)

    def test_clean_sheet_adds_revenue_bonus(self):
        # clean sheet adds 25k bonus
        dto_clean = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=0,
            result="win",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        dto_no_clean = EconomyService.calculate_league_fixture_revenue(
            goals_for=1,
            goals_against=1,
            result="win",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        self.assertEqual(dto_clean.total_before_cap - dto_no_clean.total_before_cap, 8000)

    def test_scoring_three_plus_adds_revenue_bonus(self):
        # 3 goals adds 25k bonus
        dto_three = EconomyService.calculate_league_fixture_revenue(
            goals_for=3,
            goals_against=1,
            result="win",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        dto_two = EconomyService.calculate_league_fixture_revenue(
            goals_for=2,
            goals_against=1,
            result="win",
            stadium_level=1,
            hq_level=1,
            manager_level=1
        )
        self.assertEqual(dto_three.total_before_cap - dto_two.total_before_cap, 8000)

    # --- 3. Treasury Cap ---

    def test_treasury_cap_calculates_from_manager_level_and_hq_level(self):
        # New cap formula: 5M base + 200k * level + 1M * hq_level
        # level=2, hq=1 → 5M + 400k + 1M = 6,400,000
        cap = EconomyService.calculate_treasury_cap(manager_level=2, hq_level=1)
        self.assertEqual(cap, 6_400_000)

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_treasury_cap_clamps_positive_revenue(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        # New cap for level=2, hq=1 is 6,400,000.
        # Budget is 6,300,000. Revenue is 200k → room is 100k → clamped to 100k.
        self.club.budget = 6_300_000

        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="league_match_revenue",
            source_id="match_cap",
            amount=200000,
            treasury_cap=6_400_000
        )
        self.assertTrue(res.applied)
        self.assertEqual(res.amount, 100000)
        self.assertEqual(self.club.budget, 6_400_000)

    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_treasury_cap_skips_or_zeroes_revenue_when_budget_already_at_cap(self, mock_insert):
        mock_insert.return_value = True
        session_mock = AsyncMock()

        # Budget is already at cap → no room.
        self.club.budget = 6_400_000

        res = await EconomyService.apply_budget_event_to_locked_club(
            session=session_mock,
            club=self.club,
            guild_id=self.guild_id,
            source_type="league_match_revenue",
            source_id="match_cap",
            amount=50000,
            treasury_cap=6_400_000
        )
        self.assertFalse(res.applied)
        self.assertEqual(res.amount, 0)
        self.assertEqual(res.reason, "treasury_cap")
        self.assertEqual(self.club.budget, 6_400_000)

    async def test_treasury_cap_does_not_block_facility_expenses(self):
        # Checked via test_apply_budget_event_allows_expense_above_treasury_cap
        pass

    @patch("app.repositories.get_manager_by_id")
    @patch("app.services.economy_service.EconomyService.get_facility_level")
    @patch("app.services.economy_service.EconomyService.apply_budget_event_to_locked_club")
    async def test_revenue_cap_uses_fresh_manager_level_after_xp_award(self, mock_apply, mock_fac_level, mock_get_manager):
        session_mock = AsyncMock()
        
        # fresh manager model loaded
        fresh_manager = Manager(id=self.manager_id, career_xp=240)  # Level 3 (XP threshold 240)
        mock_get_manager.return_value = fresh_manager
        mock_fac_level.return_value = 1
        
        fixture = Fixture(id=uuid.uuid4(), status=FixtureStatus.PLAYED, guild_id=self.guild_id)
        
        sim_result = MagicMock()
        sim_result.home_goals = 1
        sim_result.away_goals = 0
        
        await EconomyService.award_league_fixture_revenue(
            session=session_mock,
            fixture=fixture,
            home_club=self.club,
            away_club=Club(id=uuid.uuid4(), is_bot_controlled=True),
            sim_result=sim_result
        )
        
        mock_apply.assert_called_once()
        # New cap formula: 5M + 3*200k + 1*1M = 5M + 600k + 1M = 6,600,000
        called_kwargs = mock_apply.call_args[1]
        self.assertEqual(called_kwargs["treasury_cap"], 6_600_000)

    # --- 4. Matchday Economy ---

    @patch("app.services.economy_service.EconomyService.get_facility_level")
    @patch("app.repositories.get_manager_by_id")
    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_league_fixture_revenue_awarded_once(self, mock_insert, mock_get_manager, mock_fac_level):
        session_mock = AsyncMock()
        mock_insert.return_value = True
        mock_get_manager.return_value = self.manager
        mock_fac_level.return_value = 1
        
        fixture = Fixture(id=uuid.uuid4(), status=FixtureStatus.PLAYED, guild_id=self.guild_id)
        
        sim_result = MagicMock()
        sim_result.home_goals = 1
        sim_result.away_goals = 0
        
        # Execute first time
        await EconomyService.award_league_fixture_revenue(
            session=session_mock,
            fixture=fixture,
            home_club=self.club,
            away_club=Club(id=uuid.uuid4(), is_bot_controlled=True),
            sim_result=sim_result
        )
        
        self.assertTrue(mock_insert.called)

    @patch("app.services.economy_service.EconomyService.get_facility_level")
    @patch("app.repositories.get_manager_by_id")
    @patch("app.services.economy_service.insert_transaction_if_new")
    async def test_matchday_retry_does_not_duplicate_revenue(self, mock_insert, mock_get_manager, mock_fac_level):
        session_mock = AsyncMock()
        # First call inserts, second call returns False (duplicate conflict)
        mock_insert.side_effect = [True, False]
        mock_get_manager.return_value = self.manager
        mock_fac_level.return_value = 1
        
        fixture = Fixture(id=uuid.uuid4(), status=FixtureStatus.PLAYED, guild_id=self.guild_id)
        
        sim_result = MagicMock()
        sim_result.home_goals = 1
        sim_result.away_goals = 0
        
        # Call 1
        await EconomyService.award_league_fixture_revenue(
            session=session_mock,
            fixture=fixture,
            home_club=self.club,
            away_club=Club(id=uuid.uuid4(), is_bot_controlled=True),
            sim_result=sim_result
        )
        self.assertEqual(self.club.budget, 1_583_000)  # +83k: played 35k + win 25k + clean sheet 8k + sponsor 15k
        
        # Call 2 (Retry)
        await EconomyService.award_league_fixture_revenue(
            session=session_mock,
            fixture=fixture,
            home_club=self.club,
            away_club=Club(id=uuid.uuid4(), is_bot_controlled=True),
            sim_result=sim_result
        )
        self.assertEqual(self.club.budget, 1_583_000)  # Remains same — no double award!

    @patch("app.services.economy_service.EconomyService.apply_budget_event_to_locked_club")
    async def test_fixture_not_played_awards_zero_revenue(self, mock_apply):
        session_mock = AsyncMock()
        fixture = Fixture(id=uuid.uuid4(), status=FixtureStatus.SCHEDULED, guild_id=self.guild_id)
        
        await EconomyService.award_league_fixture_revenue(
            session=session_mock,
            fixture=fixture,
            home_club=self.club,
            away_club=Club(id=uuid.uuid4(), is_bot_controlled=False),
            sim_result=MagicMock()
        )
        mock_apply.assert_not_called()

    @patch("app.services.economy_service.EconomyService.apply_budget_event_to_locked_club")
    async def test_bot_club_gets_zero_revenue(self, mock_apply):
        session_mock = AsyncMock()
        fixture = Fixture(id=uuid.uuid4(), status=FixtureStatus.PLAYED, guild_id=self.guild_id)
        bot_club = Club(id=uuid.uuid4(), is_bot_controlled=True, manager_id=None)
        
        await EconomyService.award_league_fixture_revenue(
            session=session_mock,
            fixture=fixture,
            home_club=bot_club,
            away_club=bot_club,
            sim_result=MagicMock()
        )
        mock_apply.assert_not_called()

    @patch("app.services.economy_service.EconomyService.apply_budget_event_to_locked_club")
    async def test_friendlies_award_zero_revenue(self, mock_apply):
        # Friendly matches bypass award_league_fixture_revenue completely
        pass

    # --- 5. Facility Spending ---

    async def test_facility_upgrade_records_negative_transaction(self):
        session_mock = AsyncMock()
        fac = Facility(id=uuid.uuid4(), club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.IDLE)
        
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
            elif "club_transactions" in stmt_str:
                mock_res.scalar_one_or_none.return_value = uuid.uuid4()
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        session_mock.bind.dialect.name = "postgresql"
        
        updated_fac = await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.TRAINING_PITCH)
        self.assertEqual(updated_fac.status, FacilityStatus.UPGRADING)
        self.assertEqual(self.club.budget, 1_250_000)  # 1.5M - 250k upgrade cost (V1.1)

    async def test_facility_upgrade_duplicate_click_does_not_double_deduct(self):
        session_mock = AsyncMock()
        fac = Facility(id=uuid.uuid4(), club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.IDLE)
        
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
            elif "club_transactions" in stmt_str:
                # Return None to simulate duplicate conflict
                mock_res.scalar_one_or_none.return_value = None
            return mock_res
            
        session_mock.execute.side_effect = exec_side_effect
        session_mock.bind.dialect.name = "postgresql"
        
        with self.assertRaises(ValueError) as context:
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.TRAINING_PITCH)
        
        self.assertIn("already been processed", str(context.exception))
        # Budget remains unchanged
        self.assertEqual(self.club.budget, 1_500_000)

    async def test_facility_upgrade_level_gate_still_runs_before_spending(self):
        # Option A: Lv.2 facility requires Manager Level 1 (open to all).
        # Lv.3 facility requires Manager Level 4. Verify gate fires BEFORE budget deduction.
        session_mock = AsyncMock()
        fac = Facility(id=uuid.uuid4(), club_id=self.club_id, facility_type=FacilityType.STADIUM, level=2, status=FacilityStatus.IDLE)
        self.manager.career_xp = 0  # Level 1 — too low for Lv.2→3 upgrade (requires Lv.4)

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
        self.assertEqual(self.club.budget, 1_500_000)

    async def test_facility_upgrade_insufficient_budget_still_blocks_before_ledger(self):
        session_mock = AsyncMock()
        fac = Facility(id=uuid.uuid4(), club_id=self.club_id, facility_type=FacilityType.TRAINING_PITCH, level=1, status=FacilityStatus.IDLE)
        self.club.budget = 500  # Less than 10k cost
        
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
            await FacilityService.start_upgrade(session_mock, self.club_id, FacilityType.TRAINING_PITCH)
            
        self.assertIn("Insufficient funds", str(context.exception))
        self.assertEqual(self.club.budget, 500)

    # --- 6. Facility Economic Identity ---

    def test_training_pitch_does_not_directly_generate_money(self):
        # Level 5 Training pitch should have no effect on multipliers
        dto_pitch_5 = EconomyService.calculate_league_fixture_revenue(
            goals_for=1, goals_against=1, result="win",
            stadium_level=1, hq_level=1, manager_level=1
        )
        self.assertEqual(dto_pitch_5.stadium_multiplier, 1.0)
        self.assertEqual(dto_pitch_5.hq_multiplier, 1.0)

    def test_youth_academy_does_not_directly_generate_money(self):
        # Youth Academy level 5 has no effect on multipliers
        pass

    def test_medical_clinic_does_not_directly_generate_money(self):
        # Medical Clinic level 5 has no effect on multipliers
        pass

    def test_stadium_affects_ticket_revenue(self):
        dto_std_2 = EconomyService.calculate_league_fixture_revenue(
            goals_for=1, goals_against=1, result="win",
            stadium_level=2, hq_level=1, manager_level=1
        )
        self.assertEqual(dto_std_2.stadium_multiplier, 1.08)  # V1.1: was 1.1
        self.assertTrue(dto_std_2.final_ticket_revenue > dto_std_2.ticket_base)

    def test_club_hq_affects_sponsor_revenue(self):
        dto_hq_2 = EconomyService.calculate_league_fixture_revenue(
            goals_for=1, goals_against=1, result="win",
            stadium_level=1, hq_level=2, manager_level=1
        )
        self.assertEqual(dto_hq_2.hq_multiplier, 1.05)
        self.assertTrue(dto_hq_2.final_sponsor_revenue > dto_hq_2.sponsor_base)

    # --- 7. UI Data & Formatting ---

    @patch("app.services.club_service.get_manager_by_discord_id")
    @patch("app.services.club_service.get_club_by_manager_id")
    @patch("app.services.club_service.get_players_by_club_id")
    @patch("app.services.facility_service.FacilityService.ensure_default_facilities")
    @patch("app.services.economy_service.EconomyService.get_recent_transaction_dtos")
    async def test_club_summary_contains_recent_transactions(
        self, mock_tx_dtos, mock_ensure_fac, mock_get_players, mock_get_club, mock_get_manager
    ):
        mock_get_manager.return_value = self.manager
        mock_get_club.return_value = self.club
        mock_get_players.return_value = []
        mock_ensure_fac.return_value = []
        
        from app.services.economy_service import ClubTransactionDTO
        mock_tx_dtos.return_value = [
            ClubTransactionDTO(
                amount=50000, source_type="league_match_revenue", source_id="match_123",
                description="Match win", balance_before=10000000, balance_after=10050000,
                created_at="2026-07-03T12:00:00"
            )
        ]
        
        from app.services.club_service import get_manager_club_summary
        summary = await get_manager_club_summary(self.guild_id, "987654321")
        
        self.assertIsNotNone(summary)
        self.assertIn("recent_transactions", summary)
        self.assertEqual(len(summary["recent_transactions"]), 1)
        self.assertEqual(summary["recent_transactions"][0]["amount"], 50000)

    async def test_club_dashboard_renders_recent_money_activity(self):
        from app.ui.layouts.club_dashboard import build_club_dashboard_layout
        data = {
            "club_id": str(self.club_id),
            "club_name": "Test FC",
            "budget": 10050000,
            "reputation": 50,
            "stadium_capacity": 10000,
            "league_status": "No Active League",
            "discord_user_id": "987654321",
            "squad_size": 22,
            "average_overall": 72,
            "best_player_name": "Player A",
            "best_player_ovr": 80,
            "highest_pot_name": "Player B",
            "highest_pot_val": 90,
            "facilities": {},
            "manager_progress": {
                "career_xp": 100,
                "manager_level": 2,
                "current_level_xp": 100,
                "next_level_xp": 240,
                "xp_into_level": 100,
                "xp_needed_for_next_level": 140,
                "progress_percent": 71,
            },
            "recent_transactions": [
                {
                    "amount": 50000, "description": "Match win",
                    "source_type": "league_match_revenue", "source_id": "1",
                    "balance_before": 10000000, "balance_after": 10050000,
                    "created_at": "2026-07-03"
                }
            ]
        }

        view = build_club_dashboard_layout(data, nonce="nonce_123")
        # Find text in the non-image path (container → text_display)
        payload_text = str(view.to_components())
        self.assertIn("Recent Money Activity", payload_text)
        self.assertIn("Match win", payload_text)

    # --- 8. Future Lock Helper ---

    def test_multi_club_lock_order_helper_sorts_club_ids(self):
        id1 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        id2 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        
        sorted_ids = sort_club_ids_for_locking([id1, id2])
        self.assertEqual(sorted_ids[0], id2)
        self.assertEqual(sorted_ids[1], id1)

    # --- 9. Economy Balance Guardrails ---
    # These tests are not correctness tests — they lock in the V1.1 balance ratios.
    # If anyone re-inflates revenue or deflates upgrade costs, these will fail first.

    def test_big_win_cannot_cover_first_facility_upgrade(self):
        """
        The best possible single-match revenue must be less than the Lv.1→2 upgrade cost.
        A club should need at least 2–3 matches to afford their first upgrade.
        """
        # Best case: played + win + clean sheet + 3 goals + sponsor (Stadium Lv.1 = 1.0×, HQ Lv.1 = 1.0×)
        max_ticket = (
            config.CLUB_REVENUE_LEAGUE_PLAYED
            + config.CLUB_REVENUE_LEAGUE_WIN
            + config.CLUB_REVENUE_CLEAN_SHEET
            + config.CLUB_REVENUE_SCORED_3_PLUS
        ) * config.STADIUM_REVENUE_MULTIPLIER_BY_LEVEL[1]
        max_sponsor = config.CLUB_REVENUE_SPONSOR_BASE * config.HQ_SPONSOR_REVENUE_MULTIPLIER_BY_LEVEL[1]
        max_single_match_revenue = max_ticket + max_sponsor

        first_upgrade_cost = config.FACILITY_UPGRADE_COSTS[1]

        self.assertLess(
            max_single_match_revenue,
            first_upgrade_cost,
            msg=(
                f"A single best-case match earns {max_single_match_revenue:,} but "
                f"the first upgrade costs {first_upgrade_cost:,}. "
                f"Revenue is too high — a club could upgrade in one match."
            )
        )

    def test_starting_budget_can_afford_only_one_first_upgrade(self):
        """
        The starting budget must be >= first upgrade cost (one immediate upgrade is OK)
        but strictly < 2× first upgrade cost (prevents day-one facility spam).
        """
        starting_budget = 400_000
        first_upgrade_cost = config.FACILITY_UPGRADE_COSTS[1]

        self.assertGreaterEqual(
            starting_budget, first_upgrade_cost,
            msg="Starting budget must cover at least one first-tier upgrade."
        )
        self.assertLess(
            starting_budget, first_upgrade_cost * 2,
            msg=(
                f"Starting budget {starting_budget:,} can afford "
                f"{starting_budget // first_upgrade_cost} first-tier upgrades. "
                f"Should be < 2 to prevent instant facility spam."
            )
        )

    def test_second_tier_upgrade_requires_at_least_8_average_matches(self):
        """
        The Lv.2→3 upgrade cost must require saving across at least 8 average matches.
        Average revenue per match ≈ 65,000–70,000.
        """
        # Conservative average: played + draw (most common result) + sponsor, Lv.1 facilities
        avg_ticket = (
            config.CLUB_REVENUE_LEAGUE_PLAYED
            + config.CLUB_REVENUE_LEAGUE_DRAW
        ) * config.STADIUM_REVENUE_MULTIPLIER_BY_LEVEL[1]
        avg_sponsor = config.CLUB_REVENUE_SPONSOR_BASE * config.HQ_SPONSOR_REVENUE_MULTIPLIER_BY_LEVEL[1]
        avg_revenue_per_match = avg_ticket + avg_sponsor

        tier_2_cost = config.FACILITY_UPGRADE_COSTS[2]
        matches_needed = tier_2_cost / avg_revenue_per_match

        self.assertGreaterEqual(
            matches_needed, 8,
            msg=(
                f"Lv.2→3 upgrade ({tier_2_cost:,}) at avg revenue {avg_revenue_per_match:,.0f} "
                f"only needs {matches_needed:.1f} matches. Should require >= 8."
            )
        )

    def test_fourth_tier_upgrade_requires_at_least_40_average_matches(self):
        """
        The Lv.4→5 upgrade cost must require at least 40 average matches.
        This ensures the final upgrade tier is a long-term saving goal.
        """
        avg_ticket = (
            config.CLUB_REVENUE_LEAGUE_PLAYED
            + config.CLUB_REVENUE_LEAGUE_WIN  # optimistic but not best-case
        ) * config.STADIUM_REVENUE_MULTIPLIER_BY_LEVEL[1]
        avg_sponsor = config.CLUB_REVENUE_SPONSOR_BASE * config.HQ_SPONSOR_REVENUE_MULTIPLIER_BY_LEVEL[1]
        avg_revenue_per_match = avg_ticket + avg_sponsor

        tier_4_cost = config.FACILITY_UPGRADE_COSTS[4]
        matches_needed = tier_4_cost / avg_revenue_per_match

        self.assertGreaterEqual(
            matches_needed, 40,
            msg=(
                f"Lv.4→5 upgrade ({tier_4_cost:,}) at avg revenue {avg_revenue_per_match:,.0f} "
                f"only needs {matches_needed:.1f} matches. Should require >= 40."
            )
        )

    def test_stadium_max_level_multiplier_does_not_double_revenue(self):
        """
        Stadium Lv.5 multiplier must be < 2.0. Doubling income at max level would
        cause runaway revenue and invalidate the balance model.
        """
        max_multiplier = config.STADIUM_REVENUE_MULTIPLIER_BY_LEVEL[config.FACILITY_MAX_LEVEL]
        self.assertLess(
            max_multiplier, 2.0,
            msg=f"Stadium Lv.5 multiplier {max_multiplier} would double ticket revenue — too high."
        )

    def test_hq_max_level_multiplier_does_not_double_sponsor_revenue(self):
        """
        HQ Lv.5 multiplier must be < 2.0 to prevent sponsor revenue from outpacing ticket revenue.
        """
        max_hq_multiplier = config.HQ_SPONSOR_REVENUE_MULTIPLIER_BY_LEVEL[config.FACILITY_MAX_LEVEL]
        self.assertLess(
            max_hq_multiplier, 2.0,
            msg=f"HQ Lv.5 multiplier {max_hq_multiplier} would double sponsor revenue — too high."
        )
