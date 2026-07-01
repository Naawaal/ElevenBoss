# app/ui/renderers/lineup_renderer.py

from app.ui.components import V2View
from app.ui.layouts.lineup import build_lineup_layout

def render_lineup_screen(
    club_name: str,
    formation: str,
    starters: dict,
    bench: list,
    warnings: list[str],
    is_dirty: bool,
    nonce: str
) -> V2View:
    """
    Renders the Lineup management view payload.
    """
    return build_lineup_layout(
        club_name=club_name,
        formation=formation,
        starters=starters,
        bench=bench,
        warnings=warnings,
        is_dirty=is_dirty,
        nonce=nonce
    )
