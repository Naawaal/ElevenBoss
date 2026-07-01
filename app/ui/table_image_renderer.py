import io
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

def render_table_board(
    league_name: str, 
    season_number: int, 
    current_week: int, 
    standings: list, 
    manager_club_id: str | None = None
) -> bytes:
    """
    Generates a premium 2D visual standings table PNG image.
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
    header_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 14)
    row_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 14)
    pos_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 12)
    gd_plus_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 14)
    
    # 2. Header Section
    draw.text((60, 40), f"📊 {league_name.upper()} STANDINGS", fill=(255, 255, 255, 255), font=title_font)
    subtitle_text = f"Season {season_number}   •   Week {current_week}   •   Total Clubs: {len(standings)}"
    draw.text((60, 85), subtitle_text, fill=(0, 180, 216, 255), font=sub_font)
    draw.line([(60, 115), (1140, 115)], fill=(0, 180, 216, 100), width=2)
    
    # 3. Table Column Geometry
    col_pos = 90
    col_club = 160
    col_gp = 600
    col_w = 680
    col_d = 760
    col_l = 840
    col_gd = 940
    col_pts = 1050
    
    # Draw Column Headers
    draw.text((col_pos, 135), "POS", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_club, 135), "CLUB", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_gp, 135), "GP", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_w, 135), "W", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_d, 135), "D", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_l, 135), "L", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_gd, 135), "GD", fill=(130, 150, 180, 255), font=header_font)
    draw.text((col_pts, 135), "PTS", fill=(0, 180, 216, 255), font=header_font)
    
    draw.line([(60, 160), (1140, 160)], fill=(0, 180, 216, 50), width=1)
    
    # 4. Draw Rows
    start_y = 175
    row_h = 36  # Standard row height
    
    for idx, row in enumerate(standings):
        pos = idx + 1
        y = start_y + idx * (row_h + 4)
        
        # Check if this row belongs to the manager's club for highlighting
        is_manager = False
        if manager_club_id and str(row.club_id) == str(manager_club_id):
            is_manager = True
            
        # Draw row container background
        row_bg = (24, 38, 64, 255) if is_manager else ((14, 24, 44, 255) if idx % 2 == 0 else (10, 18, 34, 255))
        row_outline = (0, 180, 216, 180) if is_manager else None
        
        draw.rounded_rectangle(
            [60, y, 1140, y + row_h],
            radius=6,
            fill=row_bg,
            outline=row_outline,
            width=1 if row_outline else 0
        )
        
        # Draw Position Badge
        pos_badge_r = 12
        pos_center_x = col_pos + 12
        pos_center_y = y + int(row_h / 2)
        
        if pos == 1:
            draw.ellipse([pos_center_x - pos_badge_r, pos_center_y - pos_badge_r, pos_center_x + pos_badge_r, pos_center_y + pos_badge_r], fill=(255, 200, 0, 255))
            draw.text((pos_center_x - 4, pos_center_y - 7), "1", fill=(0, 0, 0, 255), font=pos_font)
        elif pos == 2:
            draw.ellipse([pos_center_x - pos_badge_r, pos_center_y - pos_badge_r, pos_center_x + pos_badge_r, pos_center_y + pos_badge_r], fill=(192, 192, 192, 255))
            draw.text((pos_center_x - 4, pos_center_y - 7), "2", fill=(0, 0, 0, 255), font=pos_font)
        elif pos == 3:
            draw.ellipse([pos_center_x - pos_badge_r, pos_center_y - pos_badge_r, pos_center_x + pos_badge_r, pos_center_y + pos_badge_r], fill=(205, 130, 50, 255))
            draw.text((pos_center_x - 4, pos_center_y - 7), "3", fill=(0, 0, 0, 255), font=pos_font)
        else:
            # Shift slightly left/right based on digit count
            shift = 4 if pos < 10 else 7
            draw.text((pos_center_x - shift, pos_center_y - 7), str(pos), fill=(200, 210, 230, 255), font=pos_font)
            
        # Draw Club Name
        club_name_text = row.club.name
        if len(club_name_text) > 35:
            club_name_text = club_name_text[:32] + "..."
            
        club_color = (255, 255, 255, 255) if not is_manager else (0, 220, 255, 255)
        draw.text((col_club, y + 10), club_name_text, fill=club_color, font=row_font)
        
        # Draw GP, W, D, L
        text_y = y + 10
        draw.text((col_gp + 2, text_y), str(row.played), fill=(200, 210, 230, 255), font=row_font)
        draw.text((col_w + 2, text_y), str(row.wins), fill=(200, 210, 230, 255), font=row_font)
        draw.text((col_d + 2, text_y), str(row.draws), fill=(200, 210, 230, 255), font=row_font)
        draw.text((col_l + 2, text_y), str(row.losses), fill=(200, 210, 230, 255), font=row_font)
        
        # Draw GD
        gd = row.goal_difference
        gd_str = f"+{gd}" if gd > 0 else (str(gd) if gd < 0 else "0")
        gd_color = (76, 175, 80, 255) if gd > 0 else ((244, 67, 54, 255) if gd < 0 else (170, 180, 200, 255))
        draw.text((col_gd + 2, text_y), gd_str, fill=gd_color, font=gd_plus_font)
        
        # Draw PTS
        draw.text((col_pts + 2, text_y), str(row.points), fill=(0, 220, 255, 255) if is_manager else (255, 255, 255, 255), font=row_font)
        
    # 5. Save to Bytes
    fp = io.BytesIO()
    im.save(fp, format="PNG")
    return fp.getvalue()
