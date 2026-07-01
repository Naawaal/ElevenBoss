"""
Fixture Renderer — Converts fixture service results into UI view models.

No Discord imports, no DB imports. Pure data transformation.
View models are consumed by fixture layout builders.
"""

from dataclasses import dataclass, field

from app.ui.components import V2View
from app.ui.layouts.fixtures import build_fixture_generation_layout, build_fixture_week_layout


# ── View Models ────────────────────────────────────────────────────

@dataclass
class FixtureRowView:
    """
    A single fixture row for display in the fixtures list.
    """
    fixture_id: str
    home_club_name: str
    away_club_name: str
    status: str
    home_goals: int | None = None
    away_goals: int | None = None


@dataclass
class FixtureWeekView:
    """
    Full view model for the weekly fixture list screen.
    """
    league_name: str
    season_number: int
    selected_week: int
    current_week: int
    min_week: int
    max_week: int
    fixtures: list[FixtureRowView] = field(default_factory=list)
    can_previous: bool = True
    can_next: bool = True


@dataclass
class FixtureGenerationView:
    """
    View model for the fixture generation success screen.
    """
    league_name: str
    season_number: int
    club_count: int
    total_weeks: int
    fixtures_per_week: int
    total_fixtures: int
    current_week: int


# ── Render Functions ───────────────────────────────────────────────

def render_fixture_generation_result(
    result,
    nonce: str,
) -> V2View:
    """
    Converts a FixtureGenerationResult into the generation success V2View.

    Args:
        result: FixtureGenerationResult from fixture_service.
        nonce: Session nonce for encoding custom IDs.

    Returns:
        V2View payload for the generation success screen.
    """
    view_model = FixtureGenerationView(
        league_name=result.league_name or "Unknown League",
        season_number=result.season_number or 1,
        club_count=result.club_count,
        total_weeks=result.total_weeks,
        fixtures_per_week=result.fixtures_per_week,
        total_fixtures=result.total_fixtures,
        current_week=result.current_week,
    )
    return build_fixture_generation_layout(view_model, nonce)


def render_fixture_week_view(
    result,
    nonce: str,
) -> V2View:
    """
    Converts a FixtureListResult (with eagerly-loaded Fixture ORM objects)
    into the weekly fixture list V2View.

    Fixture ORM objects must have their home_club and away_club relationships
    loaded (via relationship or explicit join). The renderer reads .home_club.name
    and .away_club.name directly.

    Args:
        result: FixtureListResult from fixture_service.
        nonce: Session nonce for encoding custom IDs.

    Returns:
        V2View payload for the fixture week screen.
    """
    rows: list[FixtureRowView] = []

    for fixture in (result.fixtures or []):
        home_name = (
            fixture.home_club.name
            if fixture.home_club
            else str(fixture.home_club_id)
        )
        away_name = (
            fixture.away_club.name
            if fixture.away_club
            else str(fixture.away_club_id)
        )
        rows.append(FixtureRowView(
            fixture_id=str(fixture.id),
            home_club_name=home_name,
            away_club_name=away_name,
            status=fixture.status.value if hasattr(fixture.status, "value") else str(fixture.status),
            home_goals=fixture.home_goals,
            away_goals=fixture.away_goals,
        ))

    selected = result.selected_week or 1
    current = result.current_week or 1
    min_w = result.min_week or 1
    max_w = result.max_week or 1

    view_model = FixtureWeekView(
        league_name=result.league_name or "Unknown League",
        season_number=result.season_number or 1,
        selected_week=selected,
        current_week=current,
        min_week=min_w,
        max_week=max_w,
        fixtures=rows,
        can_previous=selected > min_w,
        can_next=selected < max_w,
    )
    return build_fixture_week_layout(view_model, nonce)
