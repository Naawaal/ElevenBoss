# app/ui/renderers/matchday_renderer.py

from app.ui.components import V2View
from app.ui.layouts.matchday import (
    build_matchday_status_layout,
    build_matchday_run_layout,
)

def render_matchday_status(result, nonce: str, is_admin: bool) -> V2View:
    """
    Converts a MatchdayStatusResult into the status V2View.
    """
    return build_matchday_status_layout(result, nonce, is_admin)

def render_matchday_run(result, nonce: str) -> V2View:
    """
    Converts a MatchdayRunResult into the run results V2View.
    """
    return build_matchday_run_layout(result, nonce)
