import logging
import uuid
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, get_player_by_id, get_players_by_name

logger = logging.getLogger("app.services.player_service")

async def get_player_detail(guild_id: int | str, discord_user_id: int | str, player_id: str | uuid.UUID) -> dict | None:
    """
    Fetch a player by ID and ensure they belong to the requesting manager's club.
    Returns None if validation fails or player is not found.
    """
    try:
        if isinstance(player_id, str):
            try:
                player_uuid = uuid.UUID(player_id)
            except ValueError:
                return None
        else:
            player_uuid = player_id

        async with get_session() as session:
            manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if not manager or not manager.club_id:
                return None
            
            player = await get_player_by_id(session, player_uuid)
            if not player or player.club_id != manager.club_id:
                return None
            
            return {
                "id": str(player.id),
                "display_name": player.display_name,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "position": player.position,
                "age": player.age,
                "overall": player.overall,
                "potential": player.potential,
                "fitness": player.fitness,
                "morale": player.morale,
                "value": player.value,
                "wage": player.wage,
                "sharpness": player.sharpness,
                "preferred_foot": player.preferred_foot,
                "weak_foot": player.weak_foot,
                "skill_moves": player.skill_moves,
                "traits": player.traits or {"list": []}
            }
    except Exception as e:
        logger.error(f"Failed to fetch player detail: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e

async def search_player_by_name(guild_id: int | str, discord_user_id: int | str, query: str) -> list[dict] | None:
    """
    Searches for players in the manager's club by name query.
    Returns None if not registered.
    """
    try:
        async with get_session() as session:
            manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if not manager or not manager.club_id:
                return None
            
            players = await get_players_by_name(session, manager.club_id, query)
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
        logger.error(f"Failed to search player: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e
