import io
import discord
from dataclasses import dataclass
from app.ui.components import V2View
from app.ui.layouts.table import build_table_layout
from app.models.standing import LeagueStanding
from app.ui.table_image_renderer import render_table_board

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
    club_id: str

def render_table(
    standings: list[LeagueStanding], 
    nonce: str, 
    manager_club_id: str | None = None,
    has_image: bool = True
) -> tuple[V2View, discord.File | None]:
    """
    Renders the League Standings Table view payload along with the Pillow standings board PNG file.
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
                points=standing.points,
                club_id=str(standing.club_id)
            )
        )
        
    if not has_image:
        view = build_table_layout(view_rows, nonce, has_image=False)
        return view, None
        
    # Extract metadata from database relations
    league_name = "League Standings"
    season_number = 1
    current_week = 1
    if standings:
        first = standings[0]
        if first.season:
            season_number = first.season.season_number
            current_week = first.season.current_week
            if first.season.league:
                league_name = first.season.league.name
                
    img_bytes = render_table_board(
        league_name=league_name,
        season_number=season_number,
        current_week=current_week,
        standings=standings,
        manager_club_id=manager_club_id
    )
    
    file = discord.File(fp=io.BytesIO(img_bytes), filename="table.png")
    view = build_table_layout(view_rows, nonce, has_image=True)
    return view, file
