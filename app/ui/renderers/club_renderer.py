import discord
from app.ui.components import V2View
from app.ui.layouts import build_locker_room_layout, build_club_dashboard_layout, build_help_layout

def render_locker_room(data: dict, nonce: str) -> tuple[V2View, discord.File | None]:
    """
    Renders the Locker Room view payload from club data.
    """
    view = build_locker_room_layout(data, nonce, has_image=False)
    return view, None

def render_club_dashboard(data: dict, nonce: str) -> tuple[V2View, discord.File | None]:
    """
    Renders the Club Dashboard view payload from club data.
    """
    view = build_club_dashboard_layout(data, nonce, has_image=False)
    return view, None

def render_help(nonce: str) -> V2View:
    """
    Renders the help menu view payload.
    """
    return build_help_layout(nonce)
