import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

def format_money(amount: int) -> str:
    return f"€{amount:,}"

def draw_glass_panel(draw: ImageDraw.Draw, x1, y1, x2, y2, radius=12, fill=(18, 32, 60, 150), outline=(255, 255, 255, 50), outline_width=1):
    """
    Draws a translucent glass panel with a thin reflective border.
    """
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, outline=outline, width=outline_width)

def draw_circular_gauge(draw: ImageDraw.Draw, cx, cy, radius, value, max_value, color=(0, 244, 216, 255)):
    """
    Draws a glowing circular ring gauge.
    """
    # Background ring track
    draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=0, end=360, fill=(255, 255, 255, 25), width=6)
    
    # Progress ring segment (clock-wise starting from top)
    pct = min(1.0, max(0.0, value / max_value))
    end_angle = int(360 * pct)
    draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=-90, end=-90 + end_angle, fill=color, width=6)

def draw_glow_background(im: Image, width: int, height: int):
    """
    Creates large glowing gradient background orbs for the glassmorphic backlighting.
    """
    # Separate layer for drawing glows
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
    
    # Left gold/orange orb
    glow_draw.ellipse([100, 200, 500, 600], fill=(255, 165, 0, 30))
    # Right cyan/blue orb
    glow_draw.ellipse([700, 150, 1100, 550], fill=(0, 180, 216, 45))
    
    # Apply high blur to blend the orbs smoothly
    blurred_glow = glow_layer.filter(ImageFilter.GaussianBlur(90))
    return Image.alpha_composite(im, blurred_glow)

def draw_stadium_wireframe(draw: ImageDraw.Draw, width: int, height: int):
    """
    Draws decorative stadium blueprint gridlines in the background.
    """
    center_x, center_y = 600, 850
    # Concentric stadium circles/arcs
    for r in range(150, 750, 90):
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], outline=(0, 180, 216, 12), width=1)
    
    # Radial grid lines
    for angle in range(20, 161, 20):
        rad = math.radians(angle)
        x = center_x + int(700 * math.cos(rad))
        y = center_y - int(700 * math.sin(rad))
        draw.line([(center_x, center_y), (x, y)], fill=(0, 180, 216, 8), width=1)

def render_locker_room_board(
    club_name: str,
    manager_name: str,
    squad_size: int,
    avg_ovr: float,
    best_player_name: str,
    best_player_ovr: int,
    budget: int,
    league_status: str,
    next_action: str
) -> bytes:
    """
    Generates a premium glassmorphic visual locker room dashboard.
    """
    # 1. Canvas Setup
    width, height = 1200, 800
    im = Image.new("RGBA", (width, height), (6, 12, 26, 255))  # Dark sleek base
    draw = ImageDraw.Draw(im, "RGBA")
    
    # Background Glow & Stadium Wireframe
    im = draw_glow_background(im, width, height)
    draw = ImageDraw.Draw(im, "RGBA")  # Reinitialize draw with composited image
    draw_stadium_wireframe(draw, width, height)
    
    # Fonts
    title_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 36)
    sub_title_font = load_font(["arial.ttf", "calibri.ttf"], 16)
    section_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 22)
    badge_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 13)
    val_medium_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 24)
    val_large_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 30)
    lbl_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 12)
    text_font = load_font(["arial.ttf", "calibri.ttf"], 16)
    gauge_txt_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 18)
    
    # 2. Header
    draw.text((60, 42), f"🏟️ {club_name.upper()}", fill=(255, 255, 255, 255), font=title_font)
    draw.text((60, 88), f"Manager: {manager_name}   •   Locker Room Hub", fill=(0, 220, 255, 255), font=sub_title_font)
    
    # League Status Glass Badge
    status_text = league_status.upper()
    status_w = draw.textlength(status_text, font=badge_font)
    badge_w = int(status_w + 30)
    badge_x = 1140 - badge_w
    draw_glass_panel(draw, badge_x, 42, 1140, 78, radius=6, fill=(0, 180, 216, 40), outline=(0, 180, 216, 120), outline_width=1)
    draw.text((badge_x + 15, 51), status_text, fill=(0, 220, 255, 255), font=badge_font)
    
    # Divider Line
    draw.line([(60, 115), (1140, 115)], fill=(255, 255, 255, 30), width=1)
    
    # 3. Stats Grid (4 Glass Cards Row)
    card_w, card_h = 246, 160
    start_x, start_y = 60, 145
    spacing = 52
    
    # Card 1: Budget
    cx, cy = start_x, start_y
    draw_glass_panel(draw, cx, cy, cx + card_w, cy + card_h, fill=(12, 28, 54, 150), outline=(255, 255, 255, 35))
    # Glowing gold left-border tab
    draw.rectangle([cx, cy + 15, cx + 4, cy + card_h - 15], fill=(255, 200, 0, 255))
    draw.text((cx + 24, cy + 22), "CLUB BUDGET", fill=(150, 175, 210, 255), font=lbl_font)
    budget_short = format_money(budget)
    if len(budget_short) > 12:
         budget_short = f"€{budget / 1_000_000:.1f}M"
    draw.text((cx + 24, cy + 55), budget_short, fill=(255, 210, 0, 255), font=val_large_font)
    draw.text((cx + 24, cy + 105), "Financial Reserves", fill=(130, 150, 180, 255), font=lbl_font)
    
    # Card 2: Circular OVR Dial
    cx += card_w + spacing
    draw_glass_panel(draw, cx, cy, cx + card_w, cy + card_h, fill=(12, 28, 54, 150), outline=(255, 255, 255, 35))
    draw.text((cx + 20, cy + 22), "TEAM RATING", fill=(150, 175, 210, 255), font=lbl_font)
    
    # Circular Gauge right side
    gauge_x, gauge_y = cx + 180, cy + 85
    draw_circular_gauge(draw, gauge_x, gauge_y, radius=38, value=avg_ovr, max_value=100.0, color=(0, 244, 216, 255))
    
    # Rating Text Inside Dial
    ovr_str = f"{avg_ovr:.0f}"
    txt_w = draw.textlength(ovr_str, font=gauge_txt_font)
    draw.text((gauge_x - txt_w/2, gauge_y - 10), ovr_str, fill=(255, 255, 255, 255), font=gauge_txt_font)
    
    # Label left side
    draw.text((cx + 20, cy + 55), f"{avg_ovr:.1f}", fill=(0, 244, 216, 255), font=val_large_font)
    draw.text((cx + 20, cy + 105), "Squad Avg OVR", fill=(130, 150, 180, 255), font=lbl_font)
    
    # Card 3: Squad Size
    cx += card_w + spacing
    draw_glass_panel(draw, cx, cy, cx + card_w, cy + card_h, fill=(12, 28, 54, 150), outline=(255, 255, 255, 35))
    draw.text((cx + 24, cy + 22), "SQUAD SIZE", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((cx + 24, cy + 55), f"{squad_size}", fill=(255, 255, 255, 255), font=val_large_font)
    draw.text((cx + 24, cy + 105), "Active Squad List", fill=(130, 150, 180, 255), font=lbl_font)
    
    # Card 4: Best Player Glowing Card
    cx += card_w + spacing
    # Gold glow border
    draw_glass_panel(draw, cx, cy, cx + card_w, cy + card_h, fill=(12, 28, 54, 150), outline=(255, 215, 0, 100), outline_width=2)
    draw.text((cx + 24, cy + 22), "STAR PLAYER", fill=(255, 215, 0, 255), font=lbl_font)
    p_name = best_player_name
    if len(p_name) > 15:
        p_name = p_name[:13] + "..."
    draw.text((cx + 24, cy + 55), p_name, fill=(255, 255, 255, 255), font=val_medium_font)
    # Rating Shield Badge
    draw.rounded_rectangle([cx + 24, cy + 100, cx + 110, cy + 128], radius=4, fill=(255, 215, 0, 40), outline=(255, 215, 0, 180), width=1)
    draw.text((cx + 34, cy + 107), f"{best_player_ovr} OVR", fill=(255, 215, 0, 255), font=badge_font)
    
    # 4. Suggested Next Action Box (Futuristic Neon border)
    action_y = 340
    action_w = 1080
    action_h = 190
    draw_glass_panel(draw, 60, action_y, 60 + action_w, action_y + action_h, radius=12, fill=(10, 22, 44, 180), outline=(0, 220, 255, 120), outline_width=2)
    
    # Suggested action badge
    draw.rounded_rectangle([85, action_y + 22, 255, action_y + 54], radius=6, fill=(0, 180, 216, 220))
    draw.text((101, action_y + 30), "NEXT RECOMMENDATION", fill=(255, 255, 255, 255), font=badge_font)
    
    wrapped_action = wrap_text(next_action, 80)
    for idx, line in enumerate(wrapped_action):
        draw.text((85, action_y + 78 + idx * 26), line, fill=(210, 235, 255, 255), font=text_font)
        
    # 5. Bottom Memos Card
    stadium_y = 565
    stadium_h = 175
    draw_glass_panel(draw, 60, stadium_y, 60 + action_w, stadium_y + stadium_h, radius=12, fill=(12, 28, 54, 130), outline=(255, 255, 255, 30))
    
    draw.text((85, stadium_y + 22), "📊 SYSTEM MEMOS & TRAINING CENTER", fill=(255, 255, 255, 255), font=section_font)
    memo_1 = "• Player stamina and tactical sharpness dynamically decay over match intervals. Keep squad depth high."
    memo_2 = "• Match fixtures execute automatically. Configure starting XI and set custom tactics prior to game day."
    draw.text((85, stadium_y + 68), memo_1, fill=(160, 180, 205, 255), font=text_font)
    draw.text((85, stadium_y + 104), memo_2, fill=(160, 180, 205, 255), font=text_font)
    
    # 6. Save to Bytes
    fp = io.BytesIO()
    im.save(fp, format="PNG")
    return fp.getvalue()

def render_club_dashboard_board(
    club_name: str,
    manager_name: str,
    budget: int,
    squad_size: int,
    avg_ovr: float,
    best_player_name: str,
    best_player_ovr: int,
    highest_pot_name: str,
    highest_pot_val: int,
    stadium_capacity: int,
    league_status: str
) -> bytes:
    """
    Generates a premium glassmorphic visual club details dashboard.
    """
    # 1. Canvas Setup
    width, height = 1200, 800
    im = Image.new("RGBA", (width, height), (6, 12, 26, 255))
    draw = ImageDraw.Draw(im, "RGBA")
    
    # Background Glow & Stadium Wireframe
    im = draw_glow_background(im, width, height)
    draw = ImageDraw.Draw(im, "RGBA")
    draw_stadium_wireframe(draw, width, height)
    
    # Fonts
    title_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 36)
    sub_title_font = load_font(["arial.ttf", "calibri.ttf"], 16)
    section_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 22)
    badge_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 13)
    val_medium_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 24)
    val_large_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 30)
    lbl_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 12)
    text_font = load_font(["arial.ttf", "calibri.ttf"], 16)
    gauge_txt_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 18)
    
    # 2. Header
    draw.text((60, 42), f"📊 CLUB DETAILS — {club_name.upper()}", fill=(255, 255, 255, 255), font=title_font)
    draw.text((60, 88), f"Manager: {manager_name}   •   Club Details & Analytics", fill=(0, 220, 255, 255), font=sub_title_font)
    
    # League Status Glass Badge
    status_text = league_status.upper()
    status_w = draw.textlength(status_text, font=badge_font)
    badge_w = int(status_w + 30)
    badge_x = 1140 - badge_w
    draw_glass_panel(draw, badge_x, 42, 1140, 78, radius=6, fill=(0, 180, 216, 40), outline=(0, 180, 216, 120), outline_width=1)
    draw.text((badge_x + 15, 51), status_text, fill=(0, 220, 255, 255), font=badge_font)
    
    # Divider
    draw.line([(60, 115), (1140, 115)], fill=(255, 255, 255, 30), width=1)
    
    # 3. Left Column: Stats & Facilities
    left_x = 60
    left_w = 520
    
    # Card 1: Stadium & Facilities Details
    draw_glass_panel(draw, left_x, 145, left_x + left_w, 395, fill=(12, 28, 54, 150), outline=(255, 255, 255, 35))
    draw.text((left_x + 25, 170), "🏟️ HOME STADIUM & FACILITIES", fill=(255, 255, 255, 255), font=section_font)
    draw.line([(left_x + 25, 205), (left_x + left_w - 25, 205)], fill=(255, 255, 255, 30), width=1)
    
    draw.text((left_x + 25, 225), "STADIUM CAPACITY", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 25, 248), f"{stadium_capacity:,} Seats", fill=(255, 255, 255, 255), font=val_medium_font)
    
    draw.text((left_x + 25, 305), "FACILITIES LEVEL", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 25, 328), "Level 1 Training Ground   •   Level 1 Youth Academy", fill=(0, 220, 255, 255), font=text_font)
    
    # Card 2: Financials & Squad Overview
    draw_glass_panel(draw, left_x, 420, left_x + left_w, 740, fill=(12, 28, 54, 150), outline=(255, 255, 255, 35))
    draw.text((left_x + 25, 445), "📈 CLUB STATS OVERVIEW", fill=(255, 255, 255, 255), font=section_font)
    draw.line([(left_x + 25, 480), (left_x + left_w - 25, 480)], fill=(255, 255, 255, 30), width=1)
    
    # Mini Grid inside Left Column
    # Row 1
    draw.text((left_x + 25, 505), "BUDGET AVAILABLE", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 25, 528), format_money(budget), fill=(255, 210, 0, 255), font=val_medium_font)
    
    draw.text((left_x + 280, 505), "SQUAD SIZE", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 280, 528), f"{squad_size} Players", fill=(255, 255, 255, 255), font=val_medium_font)
    
    # Row 2
    draw.text((left_x + 25, 595), "AVERAGE OVR", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 25, 618), f"{avg_ovr:.1f} OVR", fill=(0, 244, 216, 255), font=val_medium_font)
    
    draw.text((left_x + 280, 595), "CLUB REPUTATION", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 280, 618), "⭐⭐⭐⭐⭐", fill=(255, 210, 0, 255), font=val_medium_font)
    
    # Row 3 (Tenure/Status)
    draw.text((left_x + 25, 680), "TENURE STATUS", fill=(150, 175, 210, 255), font=lbl_font)
    draw.text((left_x + 25, 700), "Active Franchise Starter", fill=(210, 235, 255, 255), font=text_font)
    
    # 4. Right Column: Star Players & Youth Talents Showcase
    right_x = 610
    right_w = 530
    
    draw_glass_panel(draw, right_x, 145, right_x + right_w, 740, fill=(10, 22, 44, 180), outline=(0, 220, 255, 80), outline_width=1)
    draw.text((right_x + 25, 170), "⭐ TEAM TALENT PROFILE", fill=(255, 255, 255, 255), font=section_font)
    draw.line([(right_x + 25, 205), (right_x + right_w - 25, 205)], fill=(255, 255, 255, 30), width=1)
    
    # Talent 1: Star Player Card (Glowing Card)
    card_1_y = 230
    draw_glass_panel(draw, right_x + 25, card_1_y, right_x + right_w - 25, card_1_y + 220, fill=(12, 28, 54, 160), outline=(255, 215, 0, 120), outline_width=2)
    
    # Badge
    draw.rounded_rectangle([right_x + 45, card_1_y + 20, right_x + 155, card_1_y + 54], radius=6, fill=(235, 60, 60, 200))
    draw.text((right_x + 59, card_1_y + 28), "STAR PLAYER", fill=(255, 255, 255, 255), font=badge_font)
    
    # Circular rating gauge right side
    star_gauge_x, star_gauge_y = right_x + right_w - 75, card_1_y + 55
    draw_circular_gauge(draw, star_gauge_x, star_gauge_y, radius=34, value=best_player_ovr, max_value=100.0, color=(255, 215, 0, 255))
    draw.text((star_gauge_x - 11, star_gauge_y - 10), str(best_player_ovr), fill=(255, 255, 255, 255), font=gauge_txt_font)
    
    draw.text((right_x + 45, card_1_y + 85), best_player_name, fill=(255, 255, 255, 255), font=val_medium_font)
    p_desc = "Current highest overall rating squad member. Crucial for matching performance under tactical simulation pressure."
    wrapped_p = wrap_text(p_desc, 38)
    for idx, line in enumerate(wrapped_p):
        draw.text((right_x + 45, card_1_y + 130 + idx * 24), line, fill=(170, 190, 215, 255), font=text_font)
        
    # Talent 2: Highest Potential Youth Prospect (Glowing Card)
    card_2_y = 480
    draw_glass_panel(draw, right_x + 25, card_2_y, right_x + right_w - 25, card_2_y + 220, fill=(12, 28, 54, 160), outline=(0, 220, 255, 120), outline_width=2)
    
    # Badge
    draw.rounded_rectangle([right_x + 45, card_2_y + 20, right_x + 165, card_2_y + 54], radius=6, fill=(40, 200, 100, 200))
    draw.text((right_x + 57, card_2_y + 28), "TOP PROSPECT", fill=(255, 255, 255, 255), font=badge_font)
    
    # Circular potential gauge right side
    pot_gauge_x, pot_gauge_y = right_x + right_w - 75, card_2_y + 55
    draw_circular_gauge(draw, pot_gauge_x, pot_gauge_y, radius=34, value=highest_pot_val, max_value=100.0, color=(0, 220, 255, 255))
    draw.text((pot_gauge_x - 11, pot_gauge_y - 10), str(highest_pot_val), fill=(255, 255, 255, 255), font=gauge_txt_font)
    
    draw.text((right_x + 45, card_2_y + 85), highest_pot_name, fill=(255, 255, 255, 255), font=val_medium_font)
    y_desc = "Highest development growth potential in the squad. Future superstar in the making with active training cycles."
    wrapped_y = wrap_text(y_desc, 38)
    for idx, line in enumerate(wrapped_y):
        draw.text((right_x + 45, card_2_y + 130 + idx * 24), line, fill=(170, 190, 215, 255), font=text_font)
        
    # 5. Save to Bytes
    fp = io.BytesIO()
    im.save(fp, format="PNG")
    return fp.getvalue()
