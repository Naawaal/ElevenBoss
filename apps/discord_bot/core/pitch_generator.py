import io
import os
import asyncio
import discord
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from match_engine import FORMATION_COORDINATES

_ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"
_RENDER_SEM = asyncio.Semaphore(10)

async def generate_squad_pitch(formation_name: str, players: list) -> discord.File:
    """
    Generates a dynamically rendered football pitch showing player positions, names, and OVRs.
    Returns a discord.File object.
    
    players: list of 11 dicts containing:
        - "name": str
        - "overall": int
        - "position": str
        - "rarity": str (optional)
    """
    # Define paths
    assets_dir = str(_ASSETS_DIR)
    pitch_path = os.path.join(assets_dir, "pitch.png")
    font_bold_path = os.path.join(assets_dir, "fonts", "Roboto-Bold.ttf")
    font_reg_path = os.path.join(assets_dir, "fonts", "Roboto-Regular.ttf")

    async with _RENDER_SEM:
        return await asyncio.to_thread(
            _render_squad_pitch, formation_name, players, pitch_path, font_bold_path, font_reg_path
        )


def _render_squad_pitch(
    formation_name: str,
    players: list,
    pitch_path: str,
    font_bold_path: str,
    font_reg_path: str,
) -> discord.File:
    # Load base pitch image
    if os.path.exists(pitch_path):
        img = Image.open(pitch_path).convert("RGBA")
    else:
        # Fallback: create a solid green pitch if image is missing
        img = Image.new("RGBA", (800, 1000), (34, 139, 34, 255))
        draw = ImageDraw.Draw(img)
        # Draw some basic pitch lines
        draw.rectangle([20, 20, 780, 980], outline=(255, 255, 255, 255), width=3)
        draw.line([20, 500, 780, 500], fill=(255, 255, 255, 255), width=3)
        draw.circle((400, 500), 80, outline=(255, 255, 255, 255), width=3)
        # Penalty areas
        draw.rectangle([200, 20, 600, 180], outline=(255, 255, 255, 255), width=3)
        draw.rectangle([200, 820, 600, 980], outline=(255, 255, 255, 255), width=3)

    width, height = img.size

    # Create overlay for transparent drawing
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Box sizes relative to image dimensions
    box_w = int(width * 0.18)
    box_h = int(height * 0.055)
    corner_radius = 6

    # Load fonts
    try:
        font_ovr = ImageFont.truetype(font_bold_path, int(box_h * 0.38))
        font_name = ImageFont.truetype(font_reg_path, int(box_h * 0.28))
    except Exception:
        font_ovr = ImageFont.load_default()
        font_name = ImageFont.load_default()

    # Get formation configuration
    if formation_name not in FORMATION_COORDINATES:
        formation_name = "4-4-2"
        
    formation_dict = FORMATION_COORDINATES[formation_name]
    coords = list(formation_dict.values())
    labels = list(formation_dict.keys())

    for idx, player in enumerate(players[:11]):
        if idx >= len(coords):
            break
            
        x_pct, y_pct = coords[idx]
        pos_label = labels[idx]

        # Map to pixel space (center of the box)
        center_x = int((x_pct / 100.0) * width)
        center_y = int((y_pct / 100.0) * height)

        # Calculate bounding box
        x0 = center_x - (box_w // 2)
        y0 = center_y - (box_h // 2)
        x1 = center_x + (box_w // 2)
        y1 = center_y + (box_h // 2)

        # Resolve colors based on OVR
        ovr = player.get("overall", 0) if player else 0
        p_name = player.get("name", "Empty") if player else "Empty"
        
        # Color coding tier: Gold, Silver, Bronze
        if ovr >= 80:
            tier_color = (255, 215, 0, 255)  # Gold
        elif ovr >= 70:
            tier_color = (192, 192, 192, 255)  # Silver
        else:
            tier_color = (205, 127, 50, 255)  # Bronze/Common

        if not player or p_name == "Empty":
            tier_color = (150, 150, 150, 200)  # Gray for empty

        # 1. Draw Player Box Background (semi-transparent dark)
        draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=corner_radius,
            fill=(15, 15, 15, 200),
            outline=tier_color,
            width=2
        )

        # 2. Draw OVR and Position Label
        if player and p_name != "Empty":
            ovr_text = f"{ovr} {pos_label}"
        else:
            ovr_text = f"-- {pos_label}"

        # Get text bounding box for alignment
        try:
            _, _, text_w, text_h = draw.textbbox((0, 0), ovr_text, font=font_ovr)
        except AttributeError:
            # Fallback for older PIL versions
            text_w, text_h = draw.textsize(ovr_text, font=font_ovr)

        # Draw OVR centered horizontally, placed in top half of box
        ovr_x = center_x - (text_w // 2)
        ovr_y = y0 + int(box_h * 0.15)
        draw.text((ovr_x, ovr_y), ovr_text, fill=tier_color, font=font_ovr)

        # 3. Draw Player Name
        # Truncate long names to fit the box
        max_chars = 14
        truncated_name = p_name
        if len(p_name) > max_chars:
            truncated_name = p_name[:max_chars-2] + ".."

        try:
            _, _, name_w, name_h = draw.textbbox((0, 0), truncated_name, font=font_name)
        except AttributeError:
            name_w, name_h = draw.textsize(truncated_name, font=font_name)

        # Draw Name centered horizontally, placed in bottom half of box
        name_x = center_x - (name_w // 2)
        name_y = y0 + int(box_h * 0.55)
        draw.text((name_x, name_y), truncated_name, fill=(255, 255, 255, 255), font=font_name)

    # Composite original image and drawing overlay
    final_img = Image.alpha_composite(img, overlay).convert("RGB")

    # Save to BytesIO
    output = io.BytesIO()
    final_img.save(output, format="PNG")
    output.seek(0)

    # Return discord.File
    return discord.File(fp=output, filename="squad_pitch.png")


async def generate_roster_grid(cards: list[dict]) -> discord.File:
    """
    Generates a visual card grid representing player cards on a roster page.
    Lays out up to 8 cards in a 4x2 grid (4 columns, 2 rows).
    """
    # Canvas configuration
    width, height = 605, 450
    img = Image.new("RGBA", (width, height), (18, 22, 28, 255))
    draw = ImageDraw.Draw(img)

    # File paths
    assets_dir = str(_ASSETS_DIR)
    font_bold_path = os.path.join(assets_dir, "fonts", "Roboto-Bold.ttf")
    font_reg_path = os.path.join(assets_dir, "fonts", "Roboto-Regular.ttf")

    async with _RENDER_SEM:
        return await asyncio.to_thread(_render_roster_grid, cards, font_bold_path, font_reg_path)


def _render_roster_grid(cards: list[dict], font_bold_path: str, font_reg_path: str) -> discord.File:
    # Card layout configurations
    card_w, card_h = 130, 190
    col_gap, row_gap = 15, 20
    margin_x, margin_y = 20, 25

    # Load fonts
    try:
        font_ovr = ImageFont.truetype(font_bold_path, 18)
        font_name = ImageFont.truetype(font_bold_path, 14)
        font_sub = ImageFont.truetype(font_reg_path, 11)
        font_id = ImageFont.truetype(font_reg_path, 10)
    except Exception:
        font_ovr = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_id = ImageFont.load_default()

    # Rarity colors map
    rarity_colors = {
        "Legendary": (255, 215, 0, 255),  # Gold
        "Epic": (163, 73, 164, 255),      # Purple
        "Rare": (0, 162, 232, 255),       # Blue
        "Common": (192, 192, 192, 255)    # Silver/Gray
    }

    for idx, card in enumerate(cards[:8]):
        # Calculate row and column index
        row = idx // 4
        col = idx % 4

        # Calculate bounding box for the card
        x0 = margin_x + col * (card_w + col_gap)
        y0 = margin_y + row * (card_h + row_gap)
        x1 = x0 + card_w
        y1 = y0 + card_h

        rarity = card.get("rarity", "Common")
        border_color = rarity_colors.get(rarity, (192, 192, 192, 255))

        # 1. Draw card background (rounded rectangle)
        draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=8,
            fill=(28, 34, 46, 255),
            outline=border_color,
            width=2
        )

        # 2. Draw OVR and Position at top of the card
        ovr = card.get("overall", 0)
        pos = card.get("position", "???")
        ovr_text = f"{ovr} {pos}"
        
        try:
            _, _, text_w, text_h = draw.textbbox((0, 0), ovr_text, font=font_ovr)
        except AttributeError:
            text_w, text_h = draw.textsize(ovr_text, font=font_ovr)

        ovr_x = x0 + (card_w - text_w) // 2
        ovr_y = y0 + 15
        draw.text((ovr_x, ovr_y), ovr_text, fill=border_color, font=font_ovr)

        # Draw a subtle separator line under OVR
        draw.line([x0 + 15, y0 + 45, x1 - 15, y0 + 45], fill=(50, 60, 78, 255), width=1)

        # 3. Draw Player Name centered
        name = card.get("name", "Unknown")
        # Truncate name
        max_chars = 12
        if len(name) > max_chars:
            name = name[:max_chars-2] + ".."

        try:
            _, _, name_w, name_h = draw.textbbox((0, 0), name, font=font_name)
        except AttributeError:
            name_w, name_h = draw.textsize(name, font=font_name)

        name_x = x0 + (card_w - name_w) // 2
        name_y = y0 + 75
        draw.text((name_x, name_y), name, fill=(255, 255, 255, 255), font=font_name)

        # 4. Draw Level and ID at the bottom
        lvl_text = f"LVL {card.get('level', 1)}"
        id_text = f"ID: {str(card.get('id', ''))[:8]}"

        try:
            _, _, lvl_w, lvl_h = draw.textbbox((0, 0), lvl_text, font=font_sub)
        except AttributeError:
            lvl_w, lvl_h = draw.textsize(lvl_text, font=font_sub)

        lvl_x = x0 + (card_w - lvl_w) // 2
        lvl_y = y0 + 120
        draw.text((lvl_x, lvl_y), lvl_text, fill=(150, 160, 175, 255), font=font_sub)

        try:
            _, _, id_w, id_h = draw.textbbox((0, 0), id_text, font=font_id)
        except AttributeError:
            id_w, id_h = draw.textsize(id_text, font=font_id)

        id_x = x0 + (card_w - id_w) // 2
        id_y = y0 + 155
        draw.text((id_x, id_y), id_text, fill=(90, 100, 115, 255), font=font_id)

    # Save to BytesIO
    output = io.BytesIO()
    img.convert("RGB").save(output, format="PNG")
    output.seek(0)

    # Return discord.File
    return discord.File(fp=output, filename="roster_grid.png")
