import logging
import uuid
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import config
from app.models.fixture import FixtureStatus
from app.repositories import insert_xp_event_if_new, add_career_xp

logger = logging.getLogger("app.services.manager_progress_service")

@dataclass(frozen=True)
class ManagerProgressDTO:
    career_xp: int
    manager_level: int
    current_level_xp: int
    next_level_xp: int | None
    xp_into_level: int
    xp_needed_for_next_level: int | None
    progress_percent: float

class ManagerProgressService:
    @staticmethod
    def calculate_level(career_xp: int) -> int:
        level = 1
        for candidate_level, required_xp in sorted(config.MANAGER_LEVEL_XP_THRESHOLDS.items()):
            if career_xp >= required_xp:
                level = candidate_level
            else:
                break
        return level

    @staticmethod
    def get_current_level_xp(level: int) -> int:
        return config.MANAGER_LEVEL_XP_THRESHOLDS.get(level, 0)

    @staticmethod
    def get_next_level_xp(level: int) -> int | None:
        return config.MANAGER_LEVEL_XP_THRESHOLDS.get(level + 1, None)

    @staticmethod
    def get_required_level_for_facility_level(next_facility_level: int) -> int:
        return config.FACILITY_MANAGER_LEVEL_REQUIREMENTS.get(next_facility_level, 1)

    @staticmethod
    def calculate_progress(career_xp: int) -> ManagerProgressDTO:
        level = ManagerProgressService.calculate_level(career_xp)
        current_xp = ManagerProgressService.get_current_level_xp(level)
        next_xp = ManagerProgressService.get_next_level_xp(level)

        if next_xp is None:
            # Max level
            return ManagerProgressDTO(
                career_xp=career_xp,
                manager_level=level,
                current_level_xp=current_xp,
                next_level_xp=None,
                xp_into_level=career_xp - current_xp,
                xp_needed_for_next_level=None,
                progress_percent=100.0
            )

        level_range = next_xp - current_xp
        xp_into = career_xp - current_xp
        xp_needed = next_xp - career_xp
        progress_pct = round((xp_into / level_range) * 100.0, 1) if level_range > 0 else 100.0

        return ManagerProgressDTO(
            career_xp=career_xp,
            manager_level=level,
            current_level_xp=current_xp,
            next_level_xp=next_xp,
            xp_into_level=xp_into,
            xp_needed_for_next_level=xp_needed,
            progress_percent=progress_pct
        )

    @staticmethod
    async def award_xp(
        session: AsyncSession,
        manager_id: uuid.UUID,
        guild_id: int | str,
        source_type: str,
        source_id: str,
        xp_amount: int,
        description: str | None = None,
    ) -> bool:
        """
        Awards Career XP to a manager for a unique event source.
        Ensures strict idempotency by recording it in the ledger first.
        """
        inserted = await insert_xp_event_if_new(
            session=session,
            manager_id=manager_id,
            guild_id=guild_id,
            source_type=source_type,
            source_id=source_id,
            xp_amount=xp_amount,
            description=description
        )

        if inserted:
            await add_career_xp(session, manager_id, xp_amount)
            logger.info(f"Awarded {xp_amount} XP to manager {manager_id} for {source_type}:{source_id}")
            return True

        logger.info(f"Skipped duplicate XP award for manager {manager_id} from {source_type}:{source_id}")
        return False

    @staticmethod
    async def award_league_fixture_xp(
        session: AsyncSession,
        fixture,
        home_club,
        away_club,
        sim_result,
    ) -> None:
        """
        Computes and awards Career XP for league matches to non-bot club managers.
        Only runs for played/completed fixtures.
        """
        if fixture.status != FixtureStatus.PLAYED:
            logger.warning(f"XP not awarded: Fixture {fixture.id} is in status '{fixture.status}', not '{FixtureStatus.PLAYED}'")
            return

        # 1. Process home club
        if not home_club.is_bot_controlled and home_club.manager_id:
            # Played XP (base)
            await ManagerProgressService.award_xp(
                session=session,
                manager_id=home_club.manager_id,
                guild_id=fixture.guild_id,
                source_type="league_fixture_played",
                source_id=f"{fixture.id}:{home_club.id}",
                xp_amount=config.MANAGER_XP_LEAGUE_PLAYED,
                description=f"League Matchday Played: {home_club.name} vs {away_club.name}"
            )

            # Win/Draw/Loss XP
            if sim_result.home_goals > sim_result.away_goals:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=home_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_win",
                    source_id=f"{fixture.id}:{home_club.id}",
                    xp_amount=config.MANAGER_XP_LEAGUE_WIN,
                    description=f"League Victory: {home_club.name} {sim_result.home_goals}–{sim_result.away_goals} {away_club.name}"
                )
            elif sim_result.home_goals < sim_result.away_goals:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=home_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_loss",
                    source_id=f"{fixture.id}:{home_club.id}",
                    xp_amount=config.MANAGER_XP_LEAGUE_LOSS,
                    description=f"League Defeat: {home_club.name} {sim_result.home_goals}–{sim_result.away_goals} {away_club.name}"
                )
            else:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=home_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_draw",
                    source_id=f"{fixture.id}:{home_club.id}",
                    xp_amount=config.MANAGER_XP_LEAGUE_DRAW,
                    description=f"League Draw: {home_club.name} {sim_result.home_goals}–{sim_result.away_goals} {away_club.name}"
                )

            # Clean sheet XP
            if sim_result.away_goals == 0:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=home_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_clean_sheet",
                    source_id=f"{fixture.id}:{home_club.id}",
                    xp_amount=config.MANAGER_XP_CLEAN_SHEET,
                    description=f"League Clean Sheet against {away_club.name}"
                )

            # Scored 3+ goals XP
            if sim_result.home_goals >= 3:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=home_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_scored_3_plus",
                    source_id=f"{fixture.id}:{home_club.id}",
                    xp_amount=config.MANAGER_XP_SCORED_3_PLUS,
                    description=f"League Match: Scored {sim_result.home_goals} goals vs {away_club.name}"
                )

        # 2. Process away club
        if not away_club.is_bot_controlled and away_club.manager_id:
            # Played XP (base)
            await ManagerProgressService.award_xp(
                session=session,
                manager_id=away_club.manager_id,
                guild_id=fixture.guild_id,
                source_type="league_fixture_played",
                source_id=f"{fixture.id}:{away_club.id}",
                xp_amount=config.MANAGER_XP_LEAGUE_PLAYED,
                description=f"League Matchday Played: {home_club.name} vs {away_club.name}"
            )

            # Win/Draw/Loss XP
            if sim_result.away_goals > sim_result.home_goals:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=away_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_win",
                    source_id=f"{fixture.id}:{away_club.id}",
                    xp_amount=config.MANAGER_XP_LEAGUE_WIN,
                    description=f"League Victory: {away_club.name} {sim_result.away_goals}–{sim_result.home_goals} {home_club.name}"
                )
            elif sim_result.away_goals < sim_result.home_goals:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=away_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_loss",
                    source_id=f"{fixture.id}:{away_club.id}",
                    xp_amount=config.MANAGER_XP_LEAGUE_LOSS,
                    description=f"League Defeat: {away_club.name} {sim_result.away_goals}–{sim_result.home_goals} {home_club.name}"
                )
            else:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=away_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_draw",
                    source_id=f"{fixture.id}:{away_club.id}",
                    xp_amount=config.MANAGER_XP_LEAGUE_DRAW,
                    description=f"League Draw: {away_club.name} {sim_result.away_goals}–{sim_result.home_goals} {home_club.name}"
                )

            # Clean sheet XP
            if sim_result.home_goals == 0:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=away_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_clean_sheet",
                    source_id=f"{fixture.id}:{away_club.id}",
                    xp_amount=config.MANAGER_XP_CLEAN_SHEET,
                    description=f"League Clean Sheet against {home_club.name}"
                )

            # Scored 3+ goals XP
            if sim_result.away_goals >= 3:
                await ManagerProgressService.award_xp(
                    session=session,
                    manager_id=away_club.manager_id,
                    guild_id=fixture.guild_id,
                    source_type="league_fixture_scored_3_plus",
                    source_id=f"{fixture.id}:{away_club.id}",
                    xp_amount=config.MANAGER_XP_SCORED_3_PLUS,
                    description=f"League Match: Scored {sim_result.away_goals} goals vs {home_club.name}"
                )
