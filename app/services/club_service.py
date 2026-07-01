import logging
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, get_club_by_manager_id, get_players_by_club_id

logger = logging.getLogger("app.services.club_service")

async def get_manager_club_summary(guild_id: int | str, discord_user_id: int | str) -> dict | None:
    """
    Returns a dictionary summarizing the club's status and key details for a manager.
    Returns None if the manager or club is not registered.
    """
    try:
        async with get_session() as session:
            manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if not manager:
                return None
            
            # Use manager's stored club_id if available, otherwise find it
            club_id = manager.club_id
            if not club_id:
                return None
                
            club = await get_club_by_manager_id(session, guild_id, manager.id)
            if not club:
                return None
            
            players = await get_players_by_club_id(session, club.id)
            squad_size = len(players)
            
            avg_ovr = round(sum(p.overall for p in players) / squad_size, 1) if squad_size > 0 else 0.0
            
            best_player = max(players, key=lambda p: p.overall) if squad_size > 0 else None
            highest_pot_player = max(players, key=lambda p: p.potential) if squad_size > 0 else None
            
            return {
                "club_id": str(club.id),
                "club_name": club.name,
                "budget": club.budget,
                "reputation": club.reputation,
                "stadium_capacity": club.stadium_capacity,
                "squad_size": squad_size,
                "average_overall": avg_ovr,
                "best_player_name": best_player.display_name if best_player else "N/A",
                "best_player_ovr": best_player.overall if best_player else 0,
                "highest_pot_name": highest_pot_player.display_name if highest_pot_player else "N/A",
                "highest_pot_val": highest_pot_player.potential if highest_pot_player else 0,
                "league_status": "No Active League", # V1 placeholders are allowed for league table
                "next_suggested_action": "View your squad details or examine player stats.",
                "discord_user_id": str(discord_user_id),
                "guild_id": str(guild_id)
            }
    except Exception as e:
        logger.error(f"Failed to fetch club summary: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e
