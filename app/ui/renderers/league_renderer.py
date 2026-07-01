import io
import discord
from dataclasses import dataclass
from app.ui.components import V2View
from app.ui.layouts.league import build_league_dashboard_layout
from app.ui.league_status_image_renderer import render_league_status_board

@dataclass
class LeagueStatusView:
    league_name: str
    status: str
    max_clubs: int
    human_clubs: int
    bot_clubs: int
    total_clubs: int
    season_number: int | None
    current_week: int | None
    can_join: bool
    can_start: bool
    next_action: str

def render_league_dashboard(
    data, 
    nonce: str, 
    is_admin: bool, 
    banner: str | None = None,
    has_image: bool = True
) -> tuple[V2View, discord.File | None]:
    """
    Renders the League Dashboard view payload using the given data.
    If has_image is True, generates a Pillow status poster image and returns it as a File.
    """
    # Map raw dictionary or status result into the LeagueStatusView model
    total_clubs = data.human_clubs + data.bot_clubs
    
    can_join = False
    can_start = False
    next_action = ""
    
    if data.status == "draft":
        can_join = total_clubs < data.league_size
        can_start = total_clubs >= 2 # Need at least 2 clubs to start the league
        if total_clubs < data.league_size:
            next_action = f"Waiting for managers to join ({total_clubs}/{data.league_size}). Admins can start to fill with bots."
        else:
            next_action = "Lobby is full! Admin can start the league season."
    elif data.status == "active":
        next_action = "Season is currently active. Matches will be simulated on schedule."
    elif data.status == "completed":
        next_action = "The league has completed. Awaiting admin reset."
        
    view_model = LeagueStatusView(
        league_name=data.league_name,
        status=data.status,
        max_clubs=data.league_size,
        human_clubs=data.human_clubs,
        bot_clubs=data.bot_clubs,
        total_clubs=total_clubs,
        season_number=data.season_number,
        current_week=data.current_week,
        can_join=can_join,
        can_start=can_start,
        next_action=next_action
    )
    
    if not has_image:
        view = build_league_dashboard_layout(view_model, nonce, is_admin, banner=banner, has_image=False)
        return view, None
        
    img_bytes = render_league_status_board(
        league_name=view_model.league_name,
        status=view_model.status,
        league_size=view_model.max_clubs,
        human_clubs=view_model.human_clubs,
        bot_clubs=view_model.bot_clubs,
        total_clubs=view_model.total_clubs,
        season_number=view_model.season_number,
        current_week=view_model.current_week,
        next_action=view_model.next_action,
        clubs_list=getattr(data, "clubs", None)
    )
    
    file = discord.File(fp=io.BytesIO(img_bytes), filename="league.png")
    view = build_league_dashboard_layout(view_model, nonce, is_admin, banner=banner, has_image=True)
    return view, file
