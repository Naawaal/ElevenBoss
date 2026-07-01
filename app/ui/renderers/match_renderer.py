# app/ui/renderers/match_renderer.py

from app.ui.components import V2View
from app.ui.layouts.match import build_match_detail_layout

def render_match_detail(result, nonce: str) -> V2View:
    """
    Converts a MatchDetailResult into the match detail report V2View.
    """
    return build_match_detail_layout(result, nonce)
