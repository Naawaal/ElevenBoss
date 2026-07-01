"""
Database repositories for data access logic
"""
from app.repositories.manager_repository import get_manager_by_discord_id, create_manager
from app.repositories.club_repository import (
    get_club_by_name, create_club, get_club_by_manager_id,
    get_user_club, get_clubs_in_league, assign_club_to_league,
    assign_club_to_season, create_bot_club
)
from app.repositories.player_repository import bulk_create_players, get_players_by_club_id, get_player_by_id, get_players_by_name, get_players_by_ids
from app.repositories.lineup_repository import get_active_lineup, save_lineup_with_players
from app.repositories.league_repository import (
    get_active_or_draft_league_by_guild, get_draft_league_by_guild,
    create_league, set_league_status, count_league_clubs
)
from app.repositories.season_repository import (
    get_latest_season_for_league, create_season, set_season_status
)
from app.repositories.standing_repository import (
    create_initial_standing, get_table_for_active_season
)


