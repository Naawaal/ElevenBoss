"""
Database repositories for data access logic
"""
from app.repositories.manager_repository import get_manager_by_discord_id, create_manager
from app.repositories.guild_config_repository import (
    get_or_create_guild_config, get_or_create_config,
    update_channels, update_admin_role, update_automation_settings,
    update_schedule_settings, set_matchday_enabled, get_settings_overview
)
from app.repositories.club_repository import (
    get_club_by_name, create_club, get_club_by_manager_id,
    get_user_club, get_clubs_in_league, assign_club_to_league,
    assign_club_to_season, create_bot_club
)
from app.repositories.player_repository import bulk_create_players, get_players_by_club_id, get_player_by_id, get_players_by_name, get_players_by_ids
from app.repositories.lineup_repository import get_active_lineup, save_lineup_with_players
from app.repositories.league_repository import (
    get_active_or_draft_league_by_guild, get_draft_league_by_guild,
    get_active_league_by_guild,
    create_league, set_league_status, count_league_clubs
)
from app.repositories.season_repository import (
    get_latest_season_for_league, get_active_season_for_league,
    create_season, set_season_status
)
from app.repositories.standing_repository import (
    create_initial_standing, get_table_for_active_season,
    get_standing_for_update, get_ranked_table
)

from app.repositories.fixture_repository import (
    fixtures_exist_for_season, bulk_create_fixtures,
    get_fixtures_by_week, get_fixtures_for_active_week,
    get_fixture_week_range, count_fixtures_for_season,
    get_current_week_fixtures_for_update, get_week_fixture_counts,
    mark_fixture_played, get_latest_played_fixture
)
from app.repositories.match_repository import (
    create_match_result, bulk_create_match_events,
    get_match_result_by_fixture, get_match_events
)
from app.repositories.scheduler_run_repository import (
    create_running_job, mark_job_success,
    mark_job_failed, get_job_by_key
)
