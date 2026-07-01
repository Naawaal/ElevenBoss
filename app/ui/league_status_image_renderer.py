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

def wrap_text(text: str, max_width_chars: int) -> list[str]:
    words = text.split()
    lines = []
    current_line = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_width_chars:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_len = len(word)
        else:
            current_line.append(word)
            current_len += len(word) + 1
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def render_league_status_board(
    league_name: str,
    status: str,
    league_size: int,
    human_clubs: int,
    bot_clubs: int,
    total_clubs: int,
    season_number: int | None,
    current_week: int | None,
    next_action: str,
    clubs_list: list[dict] | None = None
) -> bytes:
    """
    Generates a premium 2D visual league status dashboard PNG image.
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
    section_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 18)
    badge_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 14)
    stat_val_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 22)
    stat_lbl_font = load_font(["arial.ttf", "calibri.ttf"], 12)
    club_name_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 13)
    text_font = load_font(["arial.ttf", "calibri.ttf"], 13)
    pos_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 11)
    
    # 2. Header / Banner Section
    draw.text((60, 45), f"🛡️ {league_name.upper()} LEAGUE DASHBOARD", fill=(255, 255, 255, 255), font=title_font)
    
    # Status Badge
    status_upper = status.upper()
    badge_color = (76, 175, 80, 255) if status_upper == "ACTIVE" else (255, 152, 0, 255)
    draw.rounded_rectangle([960, 40, 1140, 75], radius=6, fill=badge_color)
    # Center status badge text
    status_w = draw.textlength(status_upper, font=badge_font)
    draw.text((960 + int((180 - status_w) / 2), 48), status_upper, fill=(255, 255, 255, 255), font=badge_font)
    
    draw.line([(60, 100), (1140, 100)], fill=(0, 180, 216, 100), width=2)
    
    # 3. Left Column: Stats & Next Action Widgets
    left_x = 60
    left_w = 480
    
    # Widget 1: Status
    draw.rounded_rectangle([left_x, 130, left_x + left_w, 210], radius=8, fill=(18, 30, 52, 255), outline=(0, 180, 216, 50), width=1)
    draw.text((left_x + 20, 145), "LEAGUE STATUS", fill=(130, 150, 180, 255), font=stat_lbl_font)
    status_desc = "ACTIVE SEASON" if status_upper == "ACTIVE" else "DRAFT LOBBY (WAITING)"
    draw.text((left_x + 20, 165), status_desc, fill=(255, 255, 255, 255), font=stat_val_font)
    
    # Widget 2: League Size & Counts
    draw.rounded_rectangle([left_x, 230, left_x + left_w, 310], radius=8, fill=(18, 30, 52, 255), outline=(0, 180, 216, 50), width=1)
    draw.text((left_x + 20, 245), "PARTICIPANTS", fill=(130, 150, 180, 255), font=stat_lbl_font)
    counts_desc = f"{total_clubs} / {league_size} Clubs Joined  ({human_clubs} Human, {bot_clubs} Bot)"
    draw.text((left_x + 20, 265), counts_desc, fill=(255, 255, 255, 255), font=stat_val_font)
    
    # Widget 3: Season & Week (only if active)
    draw.rounded_rectangle([left_x, 330, left_x + left_w, 410], radius=8, fill=(18, 30, 52, 255), outline=(0, 180, 216, 50), width=1)
    draw.text((left_x + 20, 345), "CURRENT TIMELINE", fill=(130, 150, 180, 255), font=stat_lbl_font)
    if status_upper == "ACTIVE" and season_number is not None:
        timeline_desc = f"Season {season_number}  •  Week {current_week}"
    else:
        timeline_desc = "Season Not Started"
    draw.text((left_x + 20, 365), timeline_desc, fill=(255, 255, 255, 255), font=stat_val_font)
    
    # Widget 4: Next Action Box
    draw.rounded_rectangle([left_x, 430, left_x + left_w, 730], radius=8, fill=(14, 25, 45, 255), outline=(0, 180, 216, 80), width=2)
    draw.rounded_rectangle([left_x + 15, 445, left_x + 130, 470], radius=4, fill=(0, 180, 216, 200))
    draw.text((left_x + 25, 450), "NEXT ACTION", fill=(255, 255, 255, 255), font=badge_font)
    
    wrapped_lines = wrap_text(next_action, 50)
    text_y_start = 490
    for idx, line in enumerate(wrapped_lines):
        draw.text((left_x + 20, text_y_start + idx * 22), line, fill=(200, 220, 240, 255), font=text_font)
        
    # 4. Right Column: Participating Clubs
    right_x = 580
    right_w = 560
    
    draw.text((right_x, 130), f"PARTICIPATING CLUBS ({total_clubs})", fill=(255, 255, 255, 255), font=section_font)
    draw.line([(right_x, 160), (right_x + right_w, 160)], fill=(0, 180, 216, 50), width=1)
    
    # Display the list of clubs
    if clubs_list:
        row_y_start = 175
        row_h = 32
        
        for idx, club in enumerate(clubs_list[:16]):  # Max 16 clubs shown in visual
            # 2-column layout for 10-16 clubs to save space
            if total_clubs > 8:
                col_idx = idx % 2
                item_idx = idx // 2
                x = right_x + col_idx * 285
                y = row_y_start + item_idx * (row_h + 4)
                w_limit = 275
            else:
                x = right_x
                y = row_y_start + idx * (row_h + 4)
                w_limit = right_w
                
            is_bot = club.get("is_bot", False)
            bg_color = (12, 22, 38, 255) if idx % 2 == 0 else (16, 28, 48, 255)
            
            draw.rounded_rectangle([x, y, x + w_limit, y + row_h], radius=4, fill=bg_color)
            
            # Badge [H] or [BOT]
            badge_lbl = "BOT" if is_bot else "H"
            badge_bg = (100, 110, 120, 255) if is_bot else (0, 180, 216, 255)
            badge_w = 40 if is_bot else 22
            draw.rounded_rectangle([x + 10, y + 6, x + 10 + badge_w, y + row_h - 6], radius=3, fill=badge_bg)
            
            lbl_shift = 6 if is_bot else 6
            draw.text((x + 10 + int((badge_w - draw.textlength(badge_lbl, font=pos_font))/2), y + 9), badge_lbl, fill=(255, 255, 255, 255), font=pos_font)
            
            # Club Name
            club_name = club.get("name", "Unknown Club")
            max_chars = 22 if total_clubs > 8 else 50
            if len(club_name) > max_chars:
                club_name = club_name[:max_chars - 3] + "..."
            draw.text((x + 20 + badge_w, y + 8), club_name, fill=(255, 255, 255, 255), font=club_name_font)
            
        if len(clubs_list) > 16:
            draw.text((right_x, 700), f"... and {len(clubs_list) - 16} more clubs.", fill=(130, 150, 180, 255), font=text_font)
    else:
        draw.text((right_x, 180), "No clubs have joined the league lobby yet.", fill=(130, 150, 180, 255), font=text_font)
        
    # 5. Save to Bytes
    fp = io.BytesIO()
    im.save(fp, format="PNG")
    return fp.getvalue()
