# app/services/economy_service.py

import logging
import uuid
from dataclasses import dataclass
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.club import Club
from app.models.facility import FacilityType, Facility
from app.models.fixture import FixtureStatus
from app.db.locking import maybe_for_update
from app.config import config
from app.repositories.economy_repository import insert_transaction_if_new

logger = logging.getLogger("app.services.economy_service")

@dataclass(frozen=True)
class BudgetEventResultDTO:
    applied: bool
    amount: int
    balance_before: int
    balance_after: int
    source_type: str
    source_id: str
    description: str | None
    reason: str | None = None
    metadata_json: dict | None = None

@dataclass(frozen=True)
class RevenueBreakdownDTO:
    ticket_base: int
    sponsor_base: int
    result_label: str
    participation_revenue: int
    result_bonus: int
    clean_sheet_bonus: int
    scored_3_plus_bonus: int
    stadium_multiplier: float
    hq_multiplier: float
    final_ticket_revenue: int
    final_sponsor_revenue: int
    total_before_cap: int
    total_after_cap: int
    treasury_cap: int | None
    clamped: bool
    description: str
    metadata_json: dict

@dataclass(frozen=True)
class ClubTransactionDTO:
    amount: int
    source_type: str
    source_id: str
    description: str | None
    balance_before: int
    balance_after: int
    created_at: str

@dataclass(frozen=True)
class FacilityUpgradeResultDTO:
    facility_type: str
    from_level: int
    to_level: int
    cost: int
    budget_before: int
    budget_after: int
    upgrade_completes_at: str

class EconomyService:
    @staticmethod
    def calculate_treasury_cap(manager_level: int, hq_level: int) -> int:
        """
        Calculates the treasury cap for a club based on its manager level and HQ facility level.
        """
        return (
            config.CLUB_TREASURY_CAP_BASE
            + manager_level * config.CLUB_TREASURY_CAP_PER_MANAGER_LEVEL
            + hq_level * config.CLUB_TREASURY_CAP_PER_HQ_LEVEL
        )

    @staticmethod
    def calculate_league_fixture_revenue(
        *,
        goals_for: int,
        goals_against: int,
        result: Literal["win", "draw", "loss"],
        stadium_level: int,
        hq_level: int,
        manager_level: int,
        current_budget: int | None = None,
    ) -> RevenueBreakdownDTO:
        """
        Computes the matchday revenue breakdown based on Stadium (ticket sales)
        and Club HQ (sponsorship) isolated multipliers.
        """
        participation = config.CLUB_REVENUE_LEAGUE_PLAYED

        if result == "win":
            result_bonus = config.CLUB_REVENUE_LEAGUE_WIN
            result_label = "Win"
        elif result == "draw":
            result_bonus = config.CLUB_REVENUE_LEAGUE_DRAW
            result_label = "Draw"
        else:
            result_bonus = config.CLUB_REVENUE_LEAGUE_LOSS
            result_label = "Loss"

        clean_sheet_bonus = (
            config.CLUB_REVENUE_CLEAN_SHEET
            if goals_against == 0
            else 0
        )

        scored_3_plus_bonus = (
            config.CLUB_REVENUE_SCORED_3_PLUS
            if goals_for >= 3
            else 0
        )

        ticket_base = (
            participation
            + result_bonus
            + clean_sheet_bonus
            + scored_3_plus_bonus
        )

        sponsor_base = config.CLUB_REVENUE_SPONSOR_BASE

        stadium_multiplier = config.STADIUM_REVENUE_MULTIPLIER_BY_LEVEL.get(stadium_level, 1.0)
        hq_multiplier = config.HQ_SPONSOR_REVENUE_MULTIPLIER_BY_LEVEL.get(hq_level, 1.0)

        final_ticket_revenue = int(ticket_base * stadium_multiplier)
        final_sponsor_revenue = int(sponsor_base * hq_multiplier)

        total_before_cap = final_ticket_revenue + final_sponsor_revenue
        
        # Calculate treasury cap
        treasury_cap = EconomyService.calculate_treasury_cap(manager_level, hq_level)

        # Clamping calculations for breakdown DTO
        clamped = False
        total_after_cap = total_before_cap
        if current_budget is not None and total_before_cap > 0:
            room = max(0, treasury_cap - current_budget)
            total_after_cap = min(total_before_cap, room)
            clamped = total_after_cap != total_before_cap

        # Detailed description line
        desc_parts = [f"League Matchday {result_label}"]
        if clean_sheet_bonus > 0:
            desc_parts.append("Clean Sheet")
        if scored_3_plus_bonus > 0:
            desc_parts.append("Scored 3+")
        description = " + ".join(desc_parts)

        metadata_json = {
            "ticket_base": ticket_base,
            "sponsor_base": sponsor_base,
            "participation_revenue": participation,
            "result_bonus": result_bonus,
            "clean_sheet_bonus": clean_sheet_bonus,
            "scored_3_plus_bonus": scored_3_plus_bonus,
            "stadium_multiplier": stadium_multiplier,
            "hq_multiplier": hq_multiplier,
            "final_ticket_revenue": final_ticket_revenue,
            "final_sponsor_revenue": final_sponsor_revenue,
            "total_before_cap": total_before_cap,
            "result": result,
        }

        return RevenueBreakdownDTO(
            ticket_base=ticket_base,
            sponsor_base=sponsor_base,
            result_label=result_label,
            participation_revenue=participation,
            result_bonus=result_bonus,
            clean_sheet_bonus=clean_sheet_bonus,
            scored_3_plus_bonus=scored_3_plus_bonus,
            stadium_multiplier=stadium_multiplier,
            hq_multiplier=hq_multiplier,
            final_ticket_revenue=final_ticket_revenue,
            final_sponsor_revenue=final_sponsor_revenue,
            total_before_cap=total_before_cap,
            total_after_cap=total_after_cap,
            treasury_cap=treasury_cap,
            clamped=clamped,
            description=description,
            metadata_json=metadata_json
        )

    @staticmethod
    async def get_facility_level(
        session: AsyncSession,
        club_id: uuid.UUID,
        facility_type: FacilityType,
    ) -> int:
        """
        Helper method to retrieve the level of a facility for a club. Defaults to 1 if not found.
        """
        stmt = select(Facility.level).where(
            Facility.club_id == club_id,
            Facility.facility_type == facility_type
        )
        res = await session.execute(stmt)
        level = res.scalar_one_or_none()
        return level if level is not None else 1

    @staticmethod
    async def apply_budget_event(
        session: AsyncSession,
        *,
        club_id: uuid.UUID,
        guild_id: str,
        source_type: str,
        source_id: str,
        amount: int,
        description: str | None = None,
        metadata_json: dict | None = None,
        treasury_cap: int | None = None,
    ) -> BudgetEventResultDTO:
        """
        Transactional wrapper that locks the club row and applies budget events.
        """
        stmt = select(Club).where(Club.id == club_id)
        stmt = maybe_for_update(stmt, session)
        res = await session.execute(stmt)
        club = res.scalar_one_or_none()
        if not club:
            raise ValueError("Club not found")

        return await EconomyService.apply_budget_event_to_locked_club(
            session=session,
            club=club,
            guild_id=guild_id,
            source_type=source_type,
            source_id=source_id,
            amount=amount,
            description=description,
            metadata_json=metadata_json,
            treasury_cap=treasury_cap
        )

    @staticmethod
    async def apply_budget_event_to_locked_club(
        session: AsyncSession,
        *,
        club: Club,
        guild_id: str,
        source_type: str,
        source_id: str,
        amount: int,
        description: str | None = None,
        metadata_json: dict | None = None,
        treasury_cap: int | None = None,
    ) -> BudgetEventResultDTO:
        """
        Performs the balance alterations on an already locked club row.
        """
        original_amount = amount
        effective_amount = amount

        if amount > 0 and treasury_cap is not None:
            # Check if already at or above cap
            if club.budget >= treasury_cap:
                return BudgetEventResultDTO(
                    applied=False,
                    amount=0,
                    balance_before=club.budget,
                    balance_after=club.budget,
                    source_type=source_type,
                    source_id=source_id,
                    description=description,
                    reason="treasury_cap",
                    metadata_json={
                        **(metadata_json or {}),
                        "original_amount": original_amount,
                        "applied_amount": 0,
                        "treasury_cap": treasury_cap,
                        "clamped": True
                    }
                )
            room = max(0, treasury_cap - club.budget)
            effective_amount = min(amount, room)

            # Check if clamping resulted in 0 effective amount
            if effective_amount == 0:
                return BudgetEventResultDTO(
                    applied=False,
                    amount=0,
                    balance_before=club.budget,
                    balance_after=club.budget,
                    source_type=source_type,
                    source_id=source_id,
                    description=description,
                    reason="treasury_cap",
                    metadata_json={
                        **(metadata_json or {}),
                        "original_amount": original_amount,
                        "applied_amount": 0,
                        "treasury_cap": treasury_cap,
                        "clamped": True
                    }
                )

        balance_before = club.budget
        balance_after = balance_before + effective_amount

        final_metadata = {
            **(metadata_json or {}),
            "original_amount": original_amount,
            "applied_amount": effective_amount,
            "treasury_cap": treasury_cap,
            "clamped": effective_amount != original_amount,
        }

        inserted = await insert_transaction_if_new(
            session=session,
            club_id=club.id,
            guild_id=guild_id,
            source_type=source_type,
            source_id=source_id,
            amount=effective_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=description,
            metadata_json=final_metadata
        )

        if not inserted:
            return BudgetEventResultDTO(
                applied=False,
                amount=0,
                balance_before=club.budget,
                balance_after=club.budget,
                source_type=source_type,
                source_id=source_id,
                description=description,
                reason="duplicate_source",
                metadata_json=final_metadata
            )

        club.budget = balance_after
        await session.flush()

        return BudgetEventResultDTO(
            applied=True,
            amount=effective_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            source_type=source_type,
            source_id=source_id,
            description=description,
            reason=None,
            metadata_json=final_metadata
        )

    @staticmethod
    async def award_league_fixture_revenue(
        session: AsyncSession,
        fixture,
        home_club,
        away_club,
        sim_result,
    ) -> None:
        """
        Computes and awards revenue for league matches. Bypasses bots and friendly matches.
        """
        if fixture.status != FixtureStatus.PLAYED:
            return

        from app.repositories import get_manager_by_id
        from app.services.manager_progress_service import ManagerProgressService

        # 1. Process home club
        if not home_club.is_bot_controlled and home_club.manager_id:
            # Query manager freshly to prevent stale manager levels
            manager = await get_manager_by_id(session, home_club.manager_id)
            if manager:
                manager_level = ManagerProgressService.calculate_level(manager.career_xp)
                stadium_level = await EconomyService.get_facility_level(session, home_club.id, FacilityType.STADIUM)
                hq_level = await EconomyService.get_facility_level(session, home_club.id, FacilityType.CLUB_HQ)

                result = "win" if sim_result.home_goals > sim_result.away_goals else ("draw" if sim_result.home_goals == sim_result.away_goals else "loss")
                revenue_dto = EconomyService.calculate_league_fixture_revenue(
                    goals_for=sim_result.home_goals,
                    goals_against=sim_result.away_goals,
                    result=result,
                    stadium_level=stadium_level,
                    hq_level=hq_level,
                    manager_level=manager_level,
                    current_budget=home_club.budget
                )

                await EconomyService.apply_budget_event_to_locked_club(
                    session=session,
                    club=home_club,
                    guild_id=fixture.guild_id,
                    source_type=config.ECONOMY_SOURCE_LEAGUE_MATCH_REVENUE,
                    source_id=f"{fixture.id}:{home_club.id}",
                    amount=revenue_dto.total_before_cap,
                    description=revenue_dto.description,
                    metadata_json=revenue_dto.metadata_json,
                    treasury_cap=revenue_dto.treasury_cap
                )

        # 2. Process away club
        if not away_club.is_bot_controlled and away_club.manager_id:
            manager = await get_manager_by_id(session, away_club.manager_id)
            if manager:
                manager_level = ManagerProgressService.calculate_level(manager.career_xp)
                stadium_level = await EconomyService.get_facility_level(session, away_club.id, FacilityType.STADIUM)
                hq_level = await EconomyService.get_facility_level(session, away_club.id, FacilityType.CLUB_HQ)

                result = "win" if sim_result.away_goals > sim_result.home_goals else ("draw" if sim_result.home_goals == sim_result.away_goals else "loss")
                revenue_dto = EconomyService.calculate_league_fixture_revenue(
                    goals_for=sim_result.away_goals,
                    goals_against=sim_result.home_goals,
                    result=result,
                    stadium_level=stadium_level,
                    hq_level=hq_level,
                    manager_level=manager_level,
                    current_budget=away_club.budget
                )

                await EconomyService.apply_budget_event_to_locked_club(
                    session=session,
                    club=away_club,
                    guild_id=fixture.guild_id,
                    source_type=config.ECONOMY_SOURCE_LEAGUE_MATCH_REVENUE,
                    source_id=f"{fixture.id}:{away_club.id}",
                    amount=revenue_dto.total_before_cap,
                    description=revenue_dto.description,
                    metadata_json=revenue_dto.metadata_json,
                    treasury_cap=revenue_dto.treasury_cap
                )

    @staticmethod
    async def get_recent_transaction_dtos(
        session: AsyncSession,
        club_id: uuid.UUID,
        limit: int = 3,
    ) -> list[ClubTransactionDTO]:
        """
        Maps recent transactions to DTOs for UI rendering.
        """
        from app.repositories.economy_repository import get_recent_transactions_by_club_id
        txs = await get_recent_transactions_by_club_id(session, club_id=club_id, limit=limit)
        return [
            ClubTransactionDTO(
                amount=tx.amount,
                source_type=tx.source_type,
                source_id=tx.source_id,
                description=tx.description,
                balance_before=tx.balance_before,
                balance_after=tx.balance_after,
                created_at=tx.created_at.isoformat()
            )
            for tx in txs
        ]
