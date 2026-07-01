from app.ui.components import V2View
from app.ui.layouts import build_locker_room_layout, build_club_dashboard_layout, build_help_layout

def render_locker_room(data: dict, nonce: str) -> V2View:
    """
    Renders the Locker Room view payload from club data.
    """
    return build_locker_room_layout(data, nonce)

def render_club_dashboard(data: dict, nonce: str) -> V2View:
    """
    Renders the Club Dashboard view payload from club data.
    """
    return build_club_dashboard_layout(data, nonce)

def render_help(nonce: str) -> V2View:
    """
    Renders the help menu view payload.
    """
    return build_help_layout(nonce)
