# app/ui/renderers/schedule_renderer.py

from app.ui.layouts.schedule import build_schedule_layout
from app.ui.components import V2View

def render_schedule_dashboard(config, nonce: str, is_admin: bool) -> V2View:
    """
    Renders the schedule control panel.
    """
    return build_schedule_layout(config, is_admin, nonce)
