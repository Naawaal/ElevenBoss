# app/ui/renderers/dm_admin_renderer.py

from app.ui.layouts.dm_admin import build_admin_dashboard_layout
from app.ui.components import V2View

def render_admin_dashboard(guild_name: str, league_status: str, season_week: str, is_admin: bool, nonce: str) -> V2View:
    return build_admin_dashboard_layout(guild_name, league_status, season_week, is_admin, nonce)
