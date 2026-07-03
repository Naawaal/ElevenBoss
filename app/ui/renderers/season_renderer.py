from app.ui.components import V2View
from app.ui.layouts.season import build_season_summary_layout

def render_season_summary(snapshot_data: dict, nonce: str) -> V2View:
    """
    Renders the season summary screen payload.
    """
    return build_season_summary_layout(snapshot_data, nonce)
