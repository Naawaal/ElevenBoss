from dataclasses import dataclass
from app.ui.components import V2View
from app.ui.layouts.table import build_table_layout
from app.models.standing import LeagueStanding

@dataclass
class StandingRowView:
    rank: int
    club_name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int

def render_table(standings: list[LeagueStanding], nonce: str) -> V2View:
    """
    Renders the League Standings Table view payload.
    """
    view_rows = []
    for idx, standing in enumerate(standings, 1):
        club_name = standing.club.name if standing.club else "Unknown Club"
        view_rows.append(
            StandingRowView(
                rank=idx,
                club_name=club_name,
                played=standing.played,
                wins=standing.wins,
                draws=standing.draws,
                losses=standing.losses,
                goals_for=standing.goals_for,
                goals_against=standing.goals_against,
                goal_difference=standing.goal_difference,
                points=standing.points
            )
        )
    return build_table_layout(view_rows, nonce)
