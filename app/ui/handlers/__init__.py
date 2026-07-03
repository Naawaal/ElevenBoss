from app.ui.handlers.session import ui_session_manager, UiSession
from app.ui.handlers.locker_room_handler import handle_open_locker_room, handle_view_club_dashboard, handle_view_help
from app.ui.handlers.squad_handler import handle_view_squad
from app.ui.handlers.player_handler import (
    handle_view_player_search,
    handle_view_player_detail,
    handle_search_player_by_name
)
from app.ui.handlers.lineup_handler import (
    handle_open_lineup_screen,
    handle_select_formation,
    handle_auto_lineup,
    handle_save_lineup,
    handle_refresh_lineup
)
from app.ui.handlers.league_handler import (
    handle_open_league_dashboard,
    handle_join_league,
    handle_start_league,
    handle_view_table,
    handle_refresh_table
)
from app.ui.handlers.fixtures_handler import (
    handle_view_current_week_fixtures,
    handle_view_week_fixtures,
)
from app.ui.handlers.matchday_handler import (
    handle_view_matchday_status,
    handle_run_matchday,
)
from app.ui.handlers.match_handler import (
    handle_view_recent_match,
    handle_view_match_detail,
)
from app.ui.handlers.season_handler import handle_view_season_summary
from app.ui.handlers.friendly_handler import (
    handle_friendly_challenge,
    handle_friendly_accept,
    handle_friendly_decline,
    handle_friendly_cancel,
    handle_friendly_skip,
    handle_friendly_practice,
    handle_friendly_practice_select
)

