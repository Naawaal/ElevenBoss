import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_session
from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.club import Club
from app.repositories import get_or_create_running_job, mark_job_success, create_season
from app.repositories.league_repository import get_latest_league_for_update
from app.repositories.club_repository import get_clubs_in_league

logger = logging.getLogger("app.services.season_reset_service")

class SeasonResetService:
    @staticmethod
    async def prepare_next_season(guild_id: int | str) -> dict:
        """
        Prepares the league for the next season by resetting the status to DRAFT
        and creating the next Season record in DRAFT status.
        """
        try:
            async with get_session() as session:
                # 1. Fetch the latest league with write-lock
                league = await get_latest_league_for_update(session, guild_id)
                if not league:
                    return {"success": False, "code": "league_not_found", "message": "No league was found in this server."}

                # 2. Check if league is completed
                if league.status != LeagueStatus.COMPLETED:
                    return {
                        "success": False,
                        "code": "league_not_completed",
                        "message": f"The league must be in COMPLETED status to prepare the next season. Current status: {league.status.value}"
                    }

                # 3. Find the completed season
                stmt = select(Season).where(Season.league_id == league.id).order_by(Season.season_number.desc())
                res = await session.execute(stmt)
                latest_season = res.scalars().first()
                
                if not latest_season or latest_season.status != SeasonStatus.COMPLETED:
                    return {
                        "success": False,
                        "code": "season_not_completed",
                        "message": "The latest season is not completed yet."
                    }

                next_season_number = latest_season.season_number + 1
                job_key = f"prepare_next_season:{guild_id}:{league.id}:{next_season_number}"

                # 4. Try acquiring job lock
                try:
                    await get_or_create_running_job(
                        session=session,
                        job_key=job_key,
                        job_type="prepare_next_season",
                        guild_id=guild_id
                    )
                    await session.flush()
                except ValueError:
                    return {
                        "success": False,
                        "code": "job_running",
                        "message": "Next season preparation is already in progress."
                    }

                # 5. Create new Season in DRAFT status
                new_season = Season(
                    guild_id=str(guild_id),
                    league_id=league.id,
                    season_number=next_season_number,
                    status=SeasonStatus.DRAFT,
                    current_week=1
                )
                session.add(new_season)
                await session.flush()

                # 6. Assign all current clubs in the league to the new draft season
                clubs = await get_clubs_in_league(session, guild_id, league.id)
                for club in clubs:
                    club.season_id = new_season.id

                # 7. Reset league status back to DRAFT to open registration
                league.status = LeagueStatus.DRAFT
                
                # Mark job success
                await mark_job_success(session, job_key)
                await session.commit()

                logger.info(f"prepare_next_season_success: guild_id={guild_id}, next_season={next_season_number}")
                return {
                    "success": True,
                    "code": "success",
                    "message": f"Season {next_season_number} prepared! League registration is now open in DRAFT status.",
                    "season_number": next_season_number,
                    "season_id": new_season.id
                }

        except Exception as e:
            logger.error(f"prepare_next_season_failed: guild_id={guild_id}, error={e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return {"success": False, "code": "database_error", "message": f"Unexpected database error: {e}"}
