"""Select empty-state helpers (022 H1 / select-empty-state contract)."""
from __future__ import annotations

from apps.discord_bot.core.view_helpers import add_select_if_options, empty_state_line


def test_empty_state_line_mentions_subject_and_recovery() -> None:
    text = empty_state_line("No patients to discharge.")
    assert "No patients" in text
    assert "Back" in text or "re-run" in text.lower()


def test_add_select_if_options_skips_empty() -> None:
    class _StubView:
        def __init__(self) -> None:
            self.children: list = []

        def add_item(self, item: object) -> None:
            self.children.append(item)

    view = _StubView()

    async def _cb(_interaction):  # pragma: no cover - not invoked
        return None

    assert add_select_if_options(
        view,  # type: ignore[arg-type]
        placeholder="x",
        options=[],
        row=0,
        callback=_cb,
    ) is None
    assert view.children == []
