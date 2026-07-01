# app/ui/layouts/lineup.py

from app.ui.components import (
    container,
    text_display,
    action_row,
    primary_button,
    secondary_button,
    success_button,
    select_menu,
    media_gallery,
    V2View
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button
from app.engine.formation_rules import get_slots_for_formation, SUPPORTED_FORMATIONS

def build_lineup_layout(
    club_name: str,
    formation: str,
    starters: dict,          # slot -> Player
    bench: list,             # list of Players
    warnings: list[str],
    is_dirty: bool,
    nonce: str,
    has_image: bool = True
) -> V2View:
    """
    Builds the Components V2 layout for the /lineup screen.
    """
    # 1. Format status and details
    status_str = "🔴 **Preview (Unsaved Changes)**" if is_dirty else "🟢 **Active / Saved**"
    
    # 2. Build content based on whether an image is shown
    if has_image:
        warnings_str = ""
        if warnings:
            warnings_str = "\n\n⚠️ **Warnings:**\n" + "\n".join(f"• {w}" for w in warnings)
            
        content = (
            f"### 📋 LINEUP & FORMATION — {club_name}\n"
            f"⚽ **Active Formation:** {formation}\n"
            f"⚡ **Status:** {status_str}\n"
            f"👥 **Bench Depth:** {len(bench)} players"
            f"{warnings_str}"
        )
    else:
        # Fallback text representation
        slots = get_slots_for_formation(formation)
        starters_lines = []
        for slot in slots:
            player = starters.get(slot)
            if player:
                name = getattr(player, "display_name")
                ovr = getattr(player, "overall")
                fit = getattr(player, "fitness", 100)
                pos = getattr(player, "position")
                starters_lines.append(f"• **{slot}**: {name} ({ovr} OVR | {pos} | 💚 {fit}%)")
            else:
                starters_lines.append(f"• **{slot}**: *Vacant*")
                
        starters_str = "\n".join(starters_lines)
        
        if bench:
            bench_str = ", ".join(f"{getattr(p, 'display_name')} ({getattr(p, 'overall')} OVR | {getattr(p, 'position')})" for p in bench)
        else:
            bench_str = "*None*"
            
        warnings_str = ""
        if warnings:
            warnings_str = "\n\n⚠️ **Warnings:**\n" + "\n".join(f"• {w}" for w in warnings)
            
        content = (
            f"### 📋 LINEUP & FORMATION — {club_name}\n"
            f"⚽ **Active Formation:** {formation}\n"
            f"⚡ **Status:** {status_str}\n\n"
            f"**Starting XI:**\n"
            f"{starters_str}\n\n"
            f"👥 **Bench (Top {len(bench)}):** {bench_str}"
            f"{warnings_str}"
        )
    
    # 3. Build Select Menu Options
    formation_options = [
        {"label": "4-4-2", "value": "4-4-2", "description": "Balanced, classic two-striker formation."},
        {"label": "4-3-3", "value": "4-3-3", "description": "Attacking shape with wingers and a single striker."},
        {"label": "4-2-3-1", "value": "4-2-3-1", "description": "Modern system with double pivots and an active CAM."},
        {"label": "3-5-2", "value": "3-5-2", "description": "Midfield-heavy shape with three central defenders."},
        {"label": "5-3-2", "value": "5-3-2", "description": "Defensive shape with active wingbacks."}
    ]
    
    # Custom IDs
    select_id = encode_custom_id("lineup", "formation", "select", nonce)
    auto_pick_id = encode_custom_id("lineup", "auto", "best", nonce)
    save_id = encode_custom_id("lineup", "save", "active", nonce)
    refresh_id = encode_custom_id("lineup", "refresh", "main", nonce)
    back_id = encode_custom_id("nav", "back", "locker", nonce)
    
    # Disable save button if lineup is incomplete (less than 11 players selected)
    is_save_disabled = (len(starters) < 11)
    
    comp_payload = []
    if has_image:
        comp_payload.append(media_gallery(["attachment://lineup.png"], ["Tactical Lineup Board"]))
    else:
        comp_payload.append(
            container([
                text_display(content)
            ])
        )
        
    comp_payload.extend([
        action_row([
            select_menu(
                custom_id=select_id,
                options=formation_options,
                placeholder=f"Select Formation (Current: {formation})"
            )
        ]),
        action_row([
            primary_button("⚡ Auto-pick Best XI", auto_pick_id),
            success_button("💾 Save Lineup", save_id, disabled=is_save_disabled)
        ]),
        action_row([
            secondary_button("🔄 Refresh", refresh_id),
            secondary_button("◀ Back to Locker Room", back_id),
            close_button(nonce)
        ])
    ])
    
    return V2View(comp_payload)
