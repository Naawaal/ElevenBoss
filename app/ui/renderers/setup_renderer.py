# app/ui/renderers/setup_renderer.py

from app.ui.layouts.setup import build_setup_layout
from app.ui.components import V2View

def render_setup_dashboard(config, nonce: str, is_admin: bool) -> V2View:
    """
    Renders the setup control panel.
    """
    return build_setup_layout(config, is_admin, nonce)
