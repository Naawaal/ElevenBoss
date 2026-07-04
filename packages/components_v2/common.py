from app.ui.components import secondary_button, danger_button
from app.ui.custom_ids import encode_custom_id

def back_button(target_scope: str, nonce: str) -> dict:
    """
    Creates a standardized Back button navigating to target_scope.
    """
    custom_id = encode_custom_id("nav", "back", target_scope, nonce)
    return secondary_button("◀ Back", custom_id)

def refresh_button(scope: str, target: str, nonce: str) -> dict:
    """
    Creates a standardized Refresh button for the current scope.
    """
    custom_id = encode_custom_id(scope, "refresh", target, nonce)
    return secondary_button("🔄 Refresh", custom_id)

def close_button(nonce: str) -> dict:
    """
    Creates a standardized Close button to dismiss the UI.
    """
    custom_id = encode_custom_id("nav", "close", "ui", nonce)
    return danger_button("✖ Close", custom_id)
