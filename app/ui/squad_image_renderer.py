import io
import math
from PIL import Image, ImageDraw, ImageFont

def load_font(font_names: list[str], size: int):
    """
    Tries loading fonts from a list of names, falling back to default if unavailable.
    """
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except IOError:
            continue
    return ImageFont.load_default()

def format_short_value(val: int) -> str:
    if val >= 1_000_000:
        return f"€{val / 1_000_000:.1f}M"
    elif val >= 1_000:
        return f"€{val / 1_000:.0f}K"
    return f"€{val}"

def render_squad_board(club_name: str, players: list[dict], page: int, total_pages: int, avg_ovr: float) -> bytes:
    """
    Generates a premium 2D visual squad grid board PNG image.
    Renders 8 players per page in a 4x2 card grid.
    """
    # 1. Canvas Setup
    width, height = 1200, 800
    im = Image.new("RGBA", (width, height), (5, 10, 20, 255))  # Dark navy base
    draw = ImageDraw.Draw(im, "RGBA")
    
    # Gradient background
    for y in range(height):
        alpha = int(255 * (1.0 - (y / height) * 0.4))
        draw.line([(0, y), (width, y)], fill=(12, 28, 48, alpha))
        
    # Fonts
    title_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 28)
    sub_font = load_font(["arial.ttf", "calibri.ttf"], 16)
    card_name_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 16)
    card_pos_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 14)
    card_ovr_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 18)
    label_font = load_font(["arial.ttf", "calibri.ttf"], 11)
    val_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 12)
    
    # 2. Header Section
    draw.text((50, 40), f"👥 {club_name.upper()} SQUAD OVERVIEW", fill=(255, 255, 255, 255), font=title_font)
    stats_text = f"Page {page} of {total_pages}   •   Average Rating: {avg_ovr:.1f} OVR   •   Total Players: {len(players)}"
    draw.text((50, 85), stats_text, fill=(0, 180, 216, 255), font=sub_font)
    draw.line([(50, 115), (1150, 115)], fill=(0, 180, 216, 100), width=2)
    
    # 3. Grid Pagination Calculations
    PAGE_SIZE = 8
    start_idx = (page - 1) * PAGE_SIZE
    page_players = players[start_idx : start_idx + PAGE_SIZE]
    
    # Card layout geometry
    card_w, card_h = 260, 260
    col_spacing, row_spacing = 20, 30
    start_x, start_y = 50, 160
    
    # Position category colors
    def get_pos_color(position: str) -> tuple[int, int, int, int]:
        p = position.upper()
        if p == "GK":
            return (255, 193, 7, 255)  # Amber
        elif p in ("CB", "LB", "RB", "LWB", "RWB"):
            return (33, 150, 243, 255)  # Blue
        elif p in ("CM", "CDM", "CAM", "LM", "RM"):
            return (76, 175, 80, 255)  # Green
        else:
            return (244, 67, 54, 255)  # Red
            
    # Draw Player Cards
    for idx, p in enumerate(page_players):
        grid_x = idx % 4
        grid_y = idx // 4
        
        x = start_x + grid_x * (card_w + col_spacing)
        y = start_y + grid_y * (card_h + row_spacing)
        
        # Draw card container
        # Round corner cards (using draw.rounded_rectangle)
        draw.rounded_rectangle(
            [x, y, x + card_w, y + card_h],
            radius=12,
            fill=(18, 30, 52, 255),
            outline=(0, 180, 216, 50),
            width=2
        )
        
        # Position badge
        pos_color = get_pos_color(p["position"])
        draw.rounded_rectangle(
            [x + 15, y + 15, x + 65, y + 40],
            radius=6,
            fill=pos_color
        )
        draw.text((x + 22, y + 19), p["position"], fill=(255, 255, 255, 255), font=card_pos_font)
        
        # OVR badge
        draw.ellipse([x + card_w - 55, y + 10, x + card_w - 15, y + 50], fill=(24, 45, 80, 255), outline=(0, 180, 216, 120), width=2)
        ovr_text = str(p["overall"])
        draw.text((x + card_w - 44, y + 20), ovr_text, fill=(255, 215, 0, 255), font=card_ovr_font)
        
        # Player display name (centered)
        name_text = p["display_name"]
        # Truncate long names
        if len(name_text) > 19:
            name_text = name_text[:17] + "..."
            
        # Draw player name text
        draw.text((x + 20, y + 70), name_text, fill=(255, 255, 255, 255), font=card_name_font)
        draw.line([(x + 20, y + 95), (x + card_w - 20, y + 95)], fill=(0, 180, 216, 40), width=1)
        
        # Info block layout (Metrics grid)
        # Row 1: AGE & FIT
        draw.text((x + 20, y + 110), "AGE", fill=(130, 150, 180, 255), font=label_font)
        draw.text((x + 20, y + 125), str(p["age"]), fill=(255, 255, 255, 255), font=val_font)
        
        draw.text((x + 140, y + 110), "FITNESS", fill=(130, 150, 180, 255), font=label_font)
        draw.text((x + 140, y + 125), f"{p['fitness']}%", fill=(255, 255, 255, 255), font=val_font)
        # Draw small fitness progress bar
        draw.rounded_rectangle([x + 140, y + 143, x + 240, y + 147], radius=2, fill=(40, 50, 70, 255))
        fit_len = int(100 * (p["fitness"] / 100.0))
        fit_bar_color = (76, 175, 80, 255) if p["fitness"] >= 75 else (255, 152, 0, 255)
        draw.rounded_rectangle([x + 140, y + 143, x + 140 + fit_len, y + 147], radius=2, fill=fit_bar_color)
        
        # Row 2: POT & MOR
        draw.text((x + 20, y + 155), "POTENTIAL", fill=(130, 150, 180, 255), font=label_font)
        draw.text((x + 20, y + 170), f"{p['potential']} POT", fill=(0, 180, 216, 255), font=val_font)
        
        draw.text((x + 140, y + 155), "MORALE", fill=(130, 150, 180, 255), font=label_font)
        draw.text((x + 140, y + 170), f"{p['morale']}%", fill=(255, 255, 255, 255), font=val_font)
        # Draw small morale progress bar
        draw.rounded_rectangle([x + 140, y + 188, x + 240, y + 192], radius=2, fill=(40, 50, 70, 255))
        mor_len = int(100 * (p["morale"] / 100.0))
        mor_bar_color = (0, 180, 216, 255) if p["morale"] >= 70 else (244, 67, 54, 255)
        draw.rounded_rectangle([x + 140, y + 188, x + 140 + mor_len, y + 192], radius=2, fill=mor_bar_color)
        
        # Row 3: VALUE & STARS
        draw.text((x + 20, y + 205), "VALUE", fill=(130, 150, 180, 255), font=label_font)
        draw.text((x + 20, y + 220), format_short_value(p["value"]), fill=(255, 255, 255, 255), font=val_font)
        
        draw.text((x + 140, y + 205), "SKILL / WF", fill=(130, 150, 180, 255), font=label_font)
        stars_str = f"SM {p['skill_moves']}★ | WF {p['weak_foot']}★"
        draw.text((x + 140, y + 220), stars_str, fill=(255, 215, 0, 255), font=val_font)
        
    # 4. Save to Bytes
    fp = io.BytesIO()
    im.save(fp, format="PNG")
    return fp.getvalue()
