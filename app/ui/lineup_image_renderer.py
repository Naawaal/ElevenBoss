# app/ui/lineup_image_renderer.py

import io
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
from app.engine.formation_positions import get_coordinates_for_formation

@dataclass
class LineupBoardPlayer:
    player_id: str
    name: str
    position: str
    slot: str
    overall: int
    potential: int | None = None
    fitness: int | None = None
    is_captain: bool = False

@dataclass
class LineupBoardData:
    club_name: str
    manager_name: str
    formation: str
    chemistry: int
    average_overall: float
    players: list[LineupBoardPlayer]
    bench_count: int
    warnings: list[str]
    is_dirty: bool = False

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

def render_lineup_board(data: LineupBoardData) -> bytes:
    """
    Generates a premium 2D visual tactical lineup board PNG image.
    """
    # 1. Image Canvas Setup
    width, height = 1200, 800
    im = Image.new("RGBA", (width, height), (5, 10, 20, 255)) # Dark navy base
    draw = ImageDraw.Draw(im, "RGBA")
    
    # Load fonts
    title_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 28)
    header_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 18)
    sub_font = load_font(["arial.ttf", "calibri.ttf"], 15)
    card_title_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 14)
    card_name_font = load_font(["arialbd.ttf", "calibrib.ttf", "arial.ttf"], 13)
    card_stat_font = load_font(["arial.ttf", "calibri.ttf"], 11)
    
    # 2. Draw Stadium Background / Pitch
    # Draw simple gradient effect for stadium lights
    for y in range(height):
        # Top is lighter navy, bottom is darker navy
        alpha = int(255 * (1.0 - (y / height) * 0.4))
        draw.line([(0, y), (width, y)], fill=(12, 28, 48, alpha))
        
    # Pitch bounds (centered, leaving space for header and footer)
    pitch_x1, pitch_y1 = 60, 120
    pitch_x2, pitch_y2 = 1140, 740
    pitch_w = pitch_x2 - pitch_x1
    pitch_h = pitch_y2 - pitch_y1
    
    # Draw tactical pitch background
    draw.rectangle([pitch_x1, pitch_y1, pitch_x2, pitch_y2], fill=(16, 85, 49, 255))
    
    # Draw horizontal grass stripes (alternating greens)
    num_stripes = 12
    stripe_h = pitch_h / num_stripes
    for i in range(num_stripes):
        if i % 2 == 1:
            sy1 = pitch_y1 + int(i * stripe_h)
            sy2 = pitch_y1 + int((i + 1) * stripe_h)
            draw.rectangle([pitch_x1, sy1, pitch_x2, sy2], fill=(20, 105, 60, 255))
            
    # Draw white pitch markings
    # Outer border line
    draw.rectangle([pitch_x1, pitch_y1, pitch_x2, pitch_y2], outline=(255, 255, 255, 120), width=3)
    # Halfway line
    mid_y = pitch_y1 + int(pitch_h / 2)
    draw.line([(pitch_x1, mid_y), (pitch_x2, mid_y)], fill=(255, 255, 255, 120), width=2)
    # Center circle
    center_x = pitch_x1 + int(pitch_w / 2)
    circle_r = 75
    draw.ellipse(
        [center_x - circle_r, mid_y - circle_r, center_x + circle_r, mid_y + circle_r],
        outline=(255, 255, 255, 120), width=2
    )
    # Penalty boxes
    box_w, box_h = 360, 130
    # Top box
    draw.rectangle(
        [center_x - box_w//2, pitch_y1, center_x + box_w//2, pitch_y1 + box_h],
        outline=(255, 255, 255, 120), width=2
    )
    # Bottom box
    draw.rectangle(
        [center_x - box_w//2, pitch_y2 - box_h, center_x + box_w//2, pitch_y2],
        outline=(255, 255, 255, 120), width=2
    )
    # Goal areas
    goal_w, goal_h = 160, 45
    draw.rectangle(
        [center_x - goal_w//2, pitch_y1, center_x + goal_w//2, pitch_y1 + goal_h],
        outline=(255, 255, 255, 120), width=2
    )
    draw.rectangle(
        [center_x - goal_w//2, pitch_y2 - goal_h, center_x + goal_w//2, pitch_y2],
        outline=(255, 255, 255, 120), width=2
    )
    
    # 3. Draw Header Overlay Bar
    draw.rectangle([0, 0, width, 100], fill=(10, 20, 30, 210))
    draw.line([(0, 100), (width, 100)], fill=(212, 175, 55, 150), width=2) # Gold bottom accent line
    
    draw.text((40, 18), "ELEVENBOSS TACTICAL BOARD", fill=(212, 175, 55, 255), font=title_font)
    
    # Draw status badge next to title
    status_text = "🔴 PREVIEW (UNSAVED)" if data.is_dirty else "🟢 ACTIVE / SAVED"
    status_color = (240, 80, 80, 255) if data.is_dirty else (100, 240, 100, 255)
    draw.text((480, 24), status_text, fill=status_color, font=header_font)
    
    draw.text((40, 58), f"Club: {data.club_name}  |  Manager: {data.manager_name}", fill=(255, 255, 255, 200), font=sub_font)
    
    stats_text = f"Formation: {data.formation}  |  Chemistry: {data.chemistry}%  |  Avg OVR: {data.average_overall:.1f}"
    draw.text((width - 450, 38), stats_text, fill=(255, 255, 255, 255), font=header_font)
    
    # 4. Position and Draw Player Cards
    try:
        coords = get_coordinates_for_formation(data.formation)
    except ValueError:
        coords = {}
        
    players_by_slot = {p.slot: p for p in data.players}
    
    card_w, card_h = 146, 82
    
    for slot, pct_coord in coords.items():
        # Translate percentages to pixels
        px_x = pitch_x1 + int((pct_coord[0] / 100.0) * pitch_w)
        px_y = pitch_y1 + int((pct_coord[1] / 100.0) * pitch_h)
        
        # Card box bounds
        x1 = px_x - card_w // 2
        y1 = px_y - card_h // 2
        x2 = px_x + card_w // 2
        y2 = px_y + card_h // 2
        
        player = players_by_slot.get(slot)
        
        if player:
            # Draw player card container (translucent dark navy glass style)
            draw.rectangle([x1, y1, x2, y2], fill=(15, 25, 45, 230), outline=(212, 175, 55, 255), width=2)
            
            # Position slot tag
            draw.text((x1 + 8, y1 + 6), slot, fill=(212, 175, 55, 255), font=card_title_font)
            
            # Overall OVR badge
            ovr_str = str(player.overall)
            draw.text((x2 - 30, y1 + 6), ovr_str, fill=(255, 255, 255, 255), font=card_title_font)
            
            # Display Name (Truncated if too long)
            name = player.name
            if len(name) > 14:
                name = name[:12] + ".."
            
            name_x = px_x - int(draw.textlength(name, font=card_name_font) // 2)
            draw.text((name_x, y1 + 32), name, fill=(255, 255, 255, 255), font=card_name_font)
            
            # Fitness Bar
            if player.fitness is not None:
                fit = max(0, min(100, player.fitness))
                bar_w = 100
                bar_h = 4
                bx1 = px_x - bar_w // 2
                by1 = y2 - 14
                bx2 = px_x + bar_w // 2
                by2 = by1 + bar_h
                
                # Bar background
                draw.rectangle([bx1, by1, bx2, by2], fill=(60, 60, 60, 255))
                
                # Bar fill (color matches health)
                fill_color = (40, 200, 80, 255) # Green
                if fit < 40:
                    fill_color = (230, 50, 50, 255) # Red
                elif fit < 70:
                    fill_color = (240, 180, 40, 255) # Amber
                    
                active_w = int(bar_w * (fit / 100.0))
                draw.rectangle([bx1, by1, bx1 + active_w, by2], fill=fill_color)
                
                # Fitness text percentage
                fit_text = f"FIT: {fit}%"
                fit_text_x = px_x - int(draw.textlength(fit_text, font=card_stat_font) // 2)
                draw.text((fit_text_x, y2 - 30), fit_text, fill=(200, 200, 200, 255), font=card_stat_font)
        else:
            # Vacant Slot Card (dotted border and dark grey fill)
            draw.rectangle([x1, y1, x2, y2], fill=(40, 40, 40, 150), outline=(200, 200, 200, 100), width=1)
            draw.text((x1 + 8, y1 + 6), slot, fill=(200, 200, 200, 150), font=card_title_font)
            
            vacant_text = "VACANT"
            vacant_x = px_x - int(draw.textlength(vacant_text, font=card_name_font) // 2)
            draw.text((vacant_x, y1 + 32), vacant_text, fill=(180, 180, 180, 100), font=card_name_font)
            
    # 5. Draw Footer Overlay Bar
    draw.rectangle([0, 750, width, height], fill=(10, 20, 30, 220))
    draw.line([(0, 750), (width, 750)], fill=(212, 175, 55, 150), width=1)
    
    bench_txt = f"👥 Bench Depth: {data.bench_count} players"
    draw.text((40, 762), bench_txt, fill=(255, 255, 255, 220), font=header_font)
    
    if data.warnings:
        warning_text = f"⚠️ {data.warnings[0]}"
        if len(data.warnings) > 1:
            warning_text += f" (+{len(data.warnings) - 1} more)"
        draw.text((width - 550, 762), warning_text, fill=(240, 100, 100, 255), font=header_font)
    else:
        success_txt = "🟢 Active lineup verified and fully optimal."
        draw.text((width - 500, 762), success_txt, fill=(100, 240, 100, 255), font=header_font)
        
    # 6. Save and Output PNG Bytes
    output = io.BytesIO()
    im.save(output, format="PNG")
    return output.getvalue()
