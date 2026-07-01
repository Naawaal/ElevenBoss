import discord
from app.ui.constants import CONTAINER, SECTION, TEXT_DISPLAY, SEPARATOR, ACTION_ROW, BUTTON, STRING_SELECT

class V2View(discord.ui.View):
    """
    Custom subclass of discord.ui.View to bypass standard serialization.
    Allows sending raw Components V2 payload.
    """
    def __init__(self, components_payload: list[dict], timeout: float | None = 900.0):
        super().__init__(timeout=timeout)
        self._components_payload = components_payload

    def has_components_v2(self) -> bool:
        return True

    def to_components(self) -> list[dict]:
        return self._components_payload

    def is_dispatchable(self) -> bool:
        # We handle interactions globally, so no need for discord.py to track this view in memory.
        return False

# ── Low-level Components V2 Payload Builders ──────────────────────

def container(components: list[dict]) -> dict:
    """
    Groups up to 10 layout components (usually Sections or Separators) in a container.
    """
    return {
        "type": CONTAINER,
        "components": components
    }

def section(text: str, accessory: dict) -> dict:
    """
    Organizes a TextDisplay alongside a required accessory component.
    """
    return {
        "type": SECTION,
        "components": [
            {
                "type": TEXT_DISPLAY,
                "content": text
            }
        ],
        "accessory": accessory
    }

def text_display(text: str) -> dict:
    """
    Renders formatted markdown text within a section or container.
    """
    return {
        "type": TEXT_DISPLAY,
        "content": text
    }

def separator(divider: bool = True, spacing: int = 1) -> dict:
    """
    Adds vertical spacing and optional horizontal divider lines between components.
    """
    return {
        "type": SEPARATOR,
        "divider": divider,
        "spacing": spacing
    }

def action_row(components: list[dict]) -> dict:
    """
    Action Row to hold interactive items (Buttons or Select Menus).
    """
    return {
        "type": ACTION_ROW,
        "components": components
    }

def button(label: str, custom_id: str, style: int = 1, disabled: bool = False) -> dict:
    """
    Raw button component.
    Styles: 1=Primary, 2=Secondary, 3=Success, 4=Danger
    """
    return {
        "type": BUTTON,
        "style": style,
        "label": label,
        "custom_id": custom_id,
        "disabled": disabled
    }

def primary_button(label: str, custom_id: str, disabled: bool = False) -> dict:
    return button(label, custom_id, style=1, disabled=disabled)

def secondary_button(label: str, custom_id: str, disabled: bool = False) -> dict:
    return button(label, custom_id, style=2, disabled=disabled)

def success_button(label: str, custom_id: str, disabled: bool = False) -> dict:
    return button(label, custom_id, style=3, disabled=disabled)

def danger_button(label: str, custom_id: str, disabled: bool = False) -> dict:
    return button(label, custom_id, style=4, disabled=disabled)

def select_menu(custom_id: str, options: list[dict], placeholder: str | None = None, disabled: bool = False) -> dict:
    """
    String select menu component.
    Options format: [{"label": "Name", "value": "val", "description": "desc"}]
    """
    menu = {
        "type": STRING_SELECT,
        "custom_id": custom_id,
        "options": options,
        "disabled": disabled
    }
    if placeholder:
        menu["placeholder"] = placeholder
    return menu
