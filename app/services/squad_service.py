import logging
import uuid
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, get_players_by_club_id

logger = logging.getLogger("app.services.squad_service")

async def get_squad(guild_id: int | str, discord_user_id: int | str) -> list[dict] | None:
    """
    Returns the list of players in the squad for the manager.
    Returns None if the manager or club is not registered.
    """
    try:
        async with get_session() as session:
            manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if not manager or not manager.club_id:
                return None
            
            players = await get_players_by_club_id(session, manager.club_id)
            return [
                {
                    "id": str(p.id),
                    "display_name": p.display_name,
                    "position": p.position,
                    "age": p.age,
                    "overall": p.overall,
                    "potential": p.potential,
                    "fitness": p.fitness,
                    "morale": p.morale,
                    "value": p.value,
                    "wage": p.wage,
                    "sharpness": p.sharpness,
                    "preferred_foot": p.preferred_foot,
                    "weak_foot": p.weak_foot,
                    "skill_moves": p.skill_moves,
                    "traits": p.traits or {"list": []}
                }
                for p in players
            ]
    except Exception as e:
        logger.error(f"Failed to fetch squad: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e
