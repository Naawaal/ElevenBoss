import io
import math
import discord
from app.ui.components import V2View
from app.ui.layouts import build_squad_layout
from app.ui.squad_image_renderer import render_squad_board

def render_squad(club_name: str, players: list[dict], page: int, nonce: str, has_image: bool = True) -> tuple[V2View, discord.File | None]:
    """
    Renders the squad page view payload. If has_image is True, generates a Pillow
    card grid image and returns it as an attachment file.
    """
    if not has_image:
        view = build_squad_layout(club_name, players, page, nonce, has_image=False)
        return view, None
        
    PAGE_SIZE = 8
    total_pages = max(1, math.ceil(len(players) / PAGE_SIZE))
    avg_ovr = sum(p["overall"] for p in players) / len(players) if players else 0.0
    
    img_bytes = render_squad_board(club_name, players, page, total_pages, avg_ovr)
    file = discord.File(fp=io.BytesIO(img_bytes), filename="squad.png")
    
    view = build_squad_layout(club_name, players, page, nonce, has_image=True)
    return view, file
