from app.ui.components import V2View
from app.ui.layouts import build_player_detail_layout, build_player_search_layout, build_player_match_select_layout

def render_player_detail(player: dict, nonce: str) -> V2View:
    """
    Renders the Player Detail layout.
    """
    return build_player_detail_layout(player, nonce)

def render_player_search(nonce: str) -> V2View:
    """
    Renders the player search instruction page layout.
    """
    return build_player_search_layout(nonce)

def render_player_matches(query: str, matches: list[dict], nonce: str) -> V2View:
    """
    Renders the multiple match selection screen layout.
    """
    return build_player_match_select_layout(query, matches, nonce)
