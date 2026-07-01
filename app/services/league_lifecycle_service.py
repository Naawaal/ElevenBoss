# app/services/league_lifecycle_service.py

import logging
from datetime import datetime
from app.db.session import get_session
from app.repositories.guild_config_repository import get_or_create_guild_config
from app.repositories.league_repository import get_draft_league_by_guild, count_league_clubs
from app.repositories.club_repository import get_clubs_in_league
from app.services.league_service import start_league, LeagueResult
from app.models.league import LeagueStatus

logger = logging.getLogger("app.services.league_lifecycle_service")

class LeagueLifecycleService:
    @staticmethod
    async def check_and_trigger_auto_start(guild_id: int | str) -> LeagueResult | None:
        """
        Check if the draft league in a guild satisfies auto-start conditions.
        If yes, trigger start_league and return the result. Otherwise return None.
        """
        try:
            async with get_session() as session:
                # 1. Fetch config and check if auto-start is enabled
                config = await get_or_create_guild_config(session, guild_id)
                if not config.auto_start_league:
                    logger.debug(f"auto_league_start_skipped: auto_start_league is disabled for guild_id={guild_id}")
                    return None

                # 2. Fetch the draft league
                league = await get_draft_league_by_guild(session, guild_id)
                if not league or league.status != LeagueStatus.DRAFT:
                    logger.debug(f"auto_league_start_skipped: no draft league in guild_id={guild_id}")
                    return None

                # 3. Check human clubs count vs minimum required
                clubs = await get_clubs_in_league(session, guild_id, league.id)
                human_clubs = [c for c in clubs if not c.is_bot_controlled]
                human_count = len(human_clubs)

                if human_count < config.minimum_human_clubs:
                    logger.info(
                        f"auto_league_start_skipped: human_count={human_count} below minimum={config.minimum_human_clubs} "
                        f"for guild_id={guild_id}"
                    )
                    return None

                # 4. Check readiness triggers
                is_full = (len(clubs) >= league.max_clubs)
                
                deadline_passed = False
                if config.registration_deadline:
                    deadline = config.registration_deadline
                    now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.utcnow()
                    deadline_passed = (now >= deadline)

                auto_fill = config.auto_fill_with_bot_clubs

                ready = is_full or deadline_passed or auto_fill
                if not ready:
                    logger.debug(
                        f"auto_league_start_skipped: draft league not ready yet for guild_id={guild_id} "
                        f"(full={is_full}, deadline_passed={deadline_passed}, auto_fill={auto_fill})"
                    )
                    return None

            # 5. Trigger start_league (outside of above session/transaction, as start_league starts its own transaction)
            logger.info(f"auto_league_start_triggered: starting league for guild_id={guild_id}")
            result = await start_league(guild_id)
            return result

        except Exception as e:
            logger.error(f"auto_league_start_failed: error during auto-start check for guild_id={guild_id}: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return None
