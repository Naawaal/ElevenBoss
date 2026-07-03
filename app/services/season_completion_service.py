import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.season import Season, SeasonStatus
from app.repositories.standing_repository import get_ranked_table
from app.repositories.season_snapshot_repository import create_season_snapshot, get_season_snapshot

logger = logging.getLogger("app.services.season_completion_service")

class SeasonCompletionService:
    @staticmethod
    async def save_final_snapshot(session: AsyncSession, guild_id: int | str, season_id: uuid.UUID) -> bool:
        """
        Calculates final statistics and saves a standings snapshot for the completed season.
        """
        try:
            # Check if snapshot already exists to be idempotent
            existing = await get_season_snapshot(session, season_id)
            if existing:
                logger.info(f"season_snapshot_exists: snapshot already saved for season_id={season_id}")
                return True

            # Fetch season details
            stmt = select(Season).where(Season.id == season_id)
            res = await session.execute(stmt)
            season = res.scalar_one_or_none()
            if not season:
                logger.warning(f"season_snapshot_failed: season_id={season_id} not found")
                return False

            # Fetch final standings
            standings = await get_ranked_table(session, guild_id, season_id)
            if not standings:
                logger.warning(f"season_snapshot_failed: no standings found for season_id={season_id}")
                return False

            # Determine champion and runner up
            champion_club_id = standings[0].club_id if len(standings) > 0 else None
            runner_up_club_id = standings[1].club_id if len(standings) > 1 else None

            # Build final table JSON
            table_rows = []
            total_goals = 0
            for i, s in enumerate(standings, start=1):
                total_goals += s.goals_for
                table_rows.append({
                    "club_id": str(s.club_id),
                    "club_name": s.club.name,
                    "played": s.played,
                    "wins": s.wins,
                    "draws": s.draws,
                    "losses": s.losses,
                    "goals_for": s.goals_for,
                    "goals_against": s.goals_against,
                    "goal_difference": s.goal_difference,
                    "points": s.points,
                    "rank": i
                })

            # Calculate total matches: sum of played divided by 2
            total_matches = sum(s.played for s in standings) // 2

            # Create and save snapshot
            await create_season_snapshot(
                session=session,
                guild_id=guild_id,
                season_id=season_id,
                league_id=season.league_id,
                season_number=season.season_number,
                champion_club_id=champion_club_id,
                runner_up_club_id=runner_up_club_id,
                final_table_json={"rows": table_rows},
                total_matches=total_matches,
                total_goals=total_goals,
                completed_at=datetime.utcnow()
            )
            logger.info(f"season_snapshot_saved: season_id={season_id}, season_number={season.season_number}")
            return True
        except Exception as e:
            logger.error(f"season_snapshot_failed_error: season_id={season_id}, error={e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return False
