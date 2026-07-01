"""
Fixture Service — Business logic for fixture retrieval.

Fixture GENERATION is handled inside league_service.start_league() as part of
the atomic season bootstrap transaction. This service only handles reading fixtures.

No Discord-specific logic. No UI rendering.
"""

import logging
from dataclasses import dataclass

from app.db.session import get_session
from app.repositories import (
    get_active_league_by_guild,
    get_active_season_for_league,
    get_fixtures_by_week,
    get_fixtures_for_active_week,
    get_fixture_week_range,
)

logger = logging.getLogger("app.services.fixture_service")


# ── Result Dataclass ───────────────────────────────────────────────

@dataclass
class FixtureListResult:
    """
    Result object returned by get_current_week_fixtures and get_fixtures_for_week.
    Contains fixtures as raw ORM objects so the renderer can hydrate club names.
    """
    success: bool
    code: str
    message: str
    league_name: str | None = None
    season_number: int | None = None
    current_week: int | None = None
    selected_week: int | None = None
    min_week: int | None = None
    max_week: int | None = None
    fixtures: list | None = None


# ── Service Functions ──────────────────────────────────────────────

async def get_current_week_fixtures(
    guild_id: int | str,
) -> FixtureListResult:
    """
    Fetches fixtures for the active season's current week.
    Returns a friendly error if the league/season/fixtures are missing.
    """
    logger.info(f"fixtures_viewed: guild_id={guild_id}")

    try:
        async with get_session() as session:
            league = await get_active_league_by_guild(session, guild_id)
            if not league:
                return FixtureListResult(
                    success=False,
                    code="league_not_found",
                    message=(
                        "No active league found in this server. "
                        "An admin can start the league with `/league start`."
                    ),
                )

            season = await get_active_season_for_league(session, guild_id, league.id)
            if not season:
                return FixtureListResult(
                    success=False,
                    code="season_not_found",
                    message="No active season found. The season may not have been started yet.",
                )

            week_range = await get_fixture_week_range(session, guild_id, season.id)
            if week_range is None:
                logger.warning(
                    f"fixtures_missing: guild_id={guild_id}, season_id={season.id} — "
                    "season is active but no fixtures found. Season may need repair."
                )
                return FixtureListResult(
                    success=False,
                    code="fixtures_missing",
                    message=(
                        "The league has started but no fixtures were found. "
                        "Please contact the bot owner — the fixture schedule may need repair."
                    ),
                    league_name=league.name,
                    season_number=season.season_number,
                )

            min_week, max_week = week_range
            current_week = season.current_week

            fixtures = await get_fixtures_for_active_week(session, guild_id, season.id, current_week)

            logger.info(
                f"fixtures_viewed: guild_id={guild_id}, season={season.season_number}, "
                f"week={current_week}, count={len(fixtures)}"
            )

            return FixtureListResult(
                success=True,
                code="success",
                message="Fixtures loaded successfully.",
                league_name=league.name,
                season_number=season.season_number,
                current_week=current_week,
                selected_week=current_week,
                min_week=min_week,
                max_week=max_week,
                fixtures=fixtures,
            )

    except Exception as e:
        logger.error(f"fixtures_error: guild_id={guild_id}, error={e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return FixtureListResult(
            success=False,
            code="unexpected_error",
            message="An unexpected error occurred while loading fixtures.",
        )


async def get_fixtures_for_week(
    guild_id: int | str,
    week: int,
) -> FixtureListResult:
    """
    Fetches fixtures for a specific week number.
    Validates that the week is within the season's valid range.
    """
    logger.info(f"fixtures_week_viewed: guild_id={guild_id}, week={week}")

    try:
        async with get_session() as session:
            league = await get_active_league_by_guild(session, guild_id)
            if not league:
                return FixtureListResult(
                    success=False,
                    code="league_not_found",
                    message=(
                        "No active league found in this server. "
                        "An admin can start the league with `/league start`."
                    ),
                )

            season = await get_active_season_for_league(session, guild_id, league.id)
            if not season:
                return FixtureListResult(
                    success=False,
                    code="season_not_found",
                    message="No active season found.",
                )

            week_range = await get_fixture_week_range(session, guild_id, season.id)
            if week_range is None:
                return FixtureListResult(
                    success=False,
                    code="fixtures_missing",
                    message=(
                        "The league has started but no fixtures were found. "
                        "Please contact the bot owner — the fixture schedule may need repair."
                    ),
                    league_name=league.name,
                    season_number=season.season_number,
                )

            min_week, max_week = week_range

            if week < min_week or week > max_week:
                logger.info(
                    f"fixtures_invalid_week: guild_id={guild_id}, week={week}, "
                    f"min={min_week}, max={max_week}"
                )
                return FixtureListResult(
                    success=False,
                    code="invalid_week",
                    message=(
                        f"Week {week} is out of range. "
                        f"Valid weeks for this season are **{min_week}** to **{max_week}**."
                    ),
                )

            fixtures = await get_fixtures_by_week(session, guild_id, season.id, week)

            logger.info(
                f"fixtures_week_viewed: guild_id={guild_id}, season={season.season_number}, "
                f"week={week}, count={len(fixtures)}"
            )

            return FixtureListResult(
                success=True,
                code="success",
                message="Fixtures loaded successfully.",
                league_name=league.name,
                season_number=season.season_number,
                current_week=season.current_week,
                selected_week=week,
                min_week=min_week,
                max_week=max_week,
                fixtures=fixtures,
            )

    except Exception as e:
        logger.error(f"fixtures_error: guild_id={guild_id}, week={week}, error={e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return FixtureListResult(
            success=False,
            code="unexpected_error",
            message="An unexpected error occurred while loading fixtures.",
        )
