from app.ui.components import V2View
from app.ui.layouts import build_squad_layout

def render_squad(club_name: str, players: list[dict], page: int, nonce: str) -> V2View:
    """
    Renders the squad page view payload.
    """
    return build_squad_layout(club_name, players, page, nonce)
