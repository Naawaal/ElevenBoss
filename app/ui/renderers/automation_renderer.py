# app/ui/renderers/automation_renderer.py

from app.ui.layouts.automation import build_automation_layout
from app.ui.components import V2View

def render_automation_dashboard(
    config,
    league_status: str,
    season_week: str,
    next_run_str: str,
    nonce: str,
    is_admin: bool
) -> V2View:
    """
    Renders the automation status panel.
    """
    return build_automation_layout(
        config=config,
        league_status=league_status,
        season_week=season_week,
        next_run_str=next_run_str,
        is_admin=is_admin,
        nonce=nonce
    )
