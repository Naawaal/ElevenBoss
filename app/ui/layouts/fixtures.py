"""
Fixture Layouts — Components V2 payload builders for the fixtures UI.

No database queries. No Discord interactions. Pure payload construction.
Consumes view model dataclasses from fixture_renderer.py.
"""

from app.ui.components import (
    container,
    text_display,
    separator,
    action_row,
    primary_button,
    secondary_button,
    success_button,
    danger_button,
    V2View,
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, back_button


def _status_emoji(status: str) -> str:
    """Maps a fixture status string to a display emoji."""
    mapping = {
        "scheduled": "🕐",
        "locked": "🔒",
        "simulating": "⚡",
        "played": "✅",
        "void": "❌",
    }
    return mapping.get(status.lower(), "📋")


def build_fixture_generation_layout(data, nonce: str) -> V2View:
    """
    Builds the Fixture Generation Success screen using Discord Components V2.

    Shows:
    - League name, season number
    - Club count, total weeks, fixtures per week, total fixtures
    - Current week indicator
    - Navigation buttons

    Args:
        data: FixtureGenerationView view model.
        nonce: Session nonce for encoding custom IDs.

    Returns:
        V2View payload.
    """
    # ── Header text ──
    text = (
        f"### 📅 FIXTURE SCHEDULE GENERATED\n"
        f"**League:** {data.league_name}\n"
        f"**Season:** Season {data.season_number}\n"
        f"\n"
        f"📊 **Summary**\n"
        f"👥 **Total Clubs:** {data.club_count}\n"
        f"📆 **Total Weeks:** {data.total_weeks}\n"
        f"⚽ **Fixtures Per Week:** {data.fixtures_per_week}\n"
        f"🗂️ **Total Fixtures:** {data.total_fixtures}\n"
        f"▶️ **Current Week:** Week {data.current_week}\n"
        f"\n"
        f"✅ All {data.total_fixtures} fixtures saved. Use `/fixtures view` to browse the schedule."
    )

    # ── Custom IDs ──
    view_fixtures_id = encode_custom_id("fixtures", "view", "current", nonce)
    view_table_id = encode_custom_id("league", "view_table", "main", nonce)
    back_locker_id = encode_custom_id("nav", "back", "locker", nonce)
    back_league_id = encode_custom_id("nav", "back", "league", nonce)

    # ── Buttons ──
    nav_row = action_row([
        success_button("📅 View Fixtures", view_fixtures_id),
        primary_button("📊 View Table", view_table_id),
        secondary_button("◀ League", back_league_id),
        secondary_button("🏠 Locker Room", back_locker_id),
        close_button(nonce),
    ])

    comp_payload = [
        container([text_display(text)]),
        nav_row,
    ]
    return V2View(comp_payload)


def build_fixture_week_layout(data, nonce: str) -> V2View:
    """
    Builds the Fixture List screen for a specific week using Discord Components V2.

    Shows:
    - League name, season, selected week / total weeks
    - List of fixture rows with home vs away club names and status
    - Prev/Next/Current week navigation (buttons disabled at boundaries)
    - Refresh, Back to League, Back to Locker Room, Close

    Args:
        data: FixtureWeekView view model.
        nonce: Session nonce for encoding custom IDs.

    Returns:
        V2View payload.
    """
    # ── Header text ──
    header = (
        f"### ⚽ FIXTURES — Week {data.selected_week} of {data.max_week}\n"
        f"**League:** {data.league_name}  |  **Season:** {data.season_number}\n"
        f"**Current Week:** Week {data.current_week}"
    )

    # ── Fixture rows ──
    if data.fixtures:
        fixture_lines = []
        for row in data.fixtures:
            emoji = _status_emoji(row.status)
            if row.status == "played" and row.home_goals is not None and row.away_goals is not None:
                score = f"**{row.home_goals}–{row.away_goals}**"
                fixture_lines.append(
                    f"{emoji} **{row.home_club_name}** {score} **{row.away_club_name}**"
                )
            else:
                fixture_lines.append(
                    f"{emoji} **{row.home_club_name}** vs **{row.away_club_name}**  ·  _{row.status.capitalize()}_"
                )
        fixtures_text = "\n".join(fixture_lines)
    else:
        fixtures_text = "_No fixtures found for this week._"

    body_text = f"**Fixtures ({len(data.fixtures)}):**\n{fixtures_text}"

    # ── Custom IDs ──
    prev_week = max(data.min_week, data.selected_week - 1)
    next_week = min(data.max_week, data.selected_week + 1)
    current_week = data.current_week

    prev_id = encode_custom_id("fixtures", "week", str(prev_week), nonce)
    next_id = encode_custom_id("fixtures", "week", str(next_week), nonce)
    current_id = encode_custom_id("fixtures", "view", "current", nonce)
    refresh_id = encode_custom_id("fixtures", "refresh", str(data.selected_week), nonce)
    back_league_id = encode_custom_id("nav", "back", "league", nonce)

    # ── Navigation row (Prev / Next / Current / Refresh / Close) ──
    nav_row = action_row([
        secondary_button("◀ Prev", prev_id, disabled=not data.can_previous),
        secondary_button("Next ▶", next_id, disabled=not data.can_next),
        primary_button("📌 Current Week", current_id),
        secondary_button("🔄 Refresh", refresh_id),
        close_button(nonce),
    ])

    # ── Back row (League / Locker Room) ──
    back_row = action_row([
        back_button("league", nonce),
        back_button("locker", nonce),
    ])

    comp_payload = [
        container([
            text_display(header),
            separator(divider=True, spacing=1),
            text_display(body_text),
        ]),
        nav_row,
        back_row,
    ]
    return V2View(comp_payload)


def build_fixture_empty_state_layout(
    message: str,
    nonce: str,
    league_name: str | None = None,
    season_number: int | None = None,
) -> V2View:
    """
    Builds a friendly empty-state or error screen for the fixtures UI.
    Used when fixtures haven't been generated, league is missing, etc.

    Args:
        message: The user-facing message to display.
        nonce: Session nonce for encoding custom IDs.
        league_name: Optional league name for context.
        season_number: Optional season number for context.

    Returns:
        V2View payload.
    """
    header = "### 📅 FIXTURES"
    if league_name:
        header += f" — {league_name}"
    if season_number:
        header += f" (Season {season_number})"

    text = f"{header}\n\n{message}"

    back_league_id = encode_custom_id("nav", "back", "league", nonce)
    back_locker_id = encode_custom_id("nav", "back", "locker", nonce)

    nav_row = action_row([
        secondary_button("◀ League", back_league_id),
        secondary_button("🏠 Locker Room", back_locker_id),
        close_button(nonce),
    ])

    comp_payload = [
        container([text_display(text)]),
        nav_row,
    ]
    return V2View(comp_payload)
