# tests/test_academy_hub_select.py
"""Academy hub enables promote/release when a single prospect is seated."""
from __future__ import annotations

from apps.discord_bot.views.academy_hub import AcademyHubView


def test_single_prospect_auto_selected_and_buttons_enabled() -> None:
    prospect = {
        "id": "abc-123",
        "name": "Youth Striker",
        "position": "FWD",
        "overall": 62,
        "age": 17,
    }
    view = AcademyHubView(
        owner_id=1,
        player={"youth_academy_level": 1},
        prospects=[prospect],
        report=None,
    )

    assert view.selected_id == "abc-123"
    assert view.promote_btn.disabled is False
    assert view.release_btn.disabled is False
