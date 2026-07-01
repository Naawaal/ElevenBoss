import math
from app.ui.components import container, text_display, action_row, secondary_button, select_menu, media_gallery, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button, back_button

PAGE_SIZE = 8

def build_squad_table(players: list[dict], page: int, page_size: int) -> str:
    """
    Constructs a monospaced ASCII table of the players on the current page.
    """
    start_idx = (page - 1) * page_size
    page_players = players[start_idx : start_idx + page_size]
    
    if not page_players:
        return "*No players found in your squad.*"
        
    lines = []
    lines.append("` Pos  Name                 Age  OVR  POT  Fit  Mor `")
    lines.append("`──────────────────────────────────────────────────`")
    for p in page_players:
        display_name = p["display_name"]
        if len(display_name) > 20:
            display_name = display_name[:17] + "..."
            
        pos = p["position"].ljust(4)
        name = display_name.ljust(20)
        age = str(p["age"]).ljust(4)
        ovr = str(p["overall"]).ljust(5)
        pot = str(p["potential"]).ljust(5)
        fit = f"{p['fitness']}%".ljust(5)
        mor = f"{p['morale']}%"
        
        lines.append(f"` {pos} {name} {age} {ovr} {pot} {fit} {mor} `")
        
    return "\n".join(lines)

def build_squad_layout(
    club_name: str,
    players: list[dict],
    page: int,
    nonce: str,
    has_image: bool = False
) -> V2View:
    """
    Builds the Squad Overview layout. If has_image is True, renders
    the dynamic Pillow card grid inside a Media Gallery. Fallback to ASCII table.
    """
    total_players = len(players)
    total_pages = max(1, math.ceil(total_players / PAGE_SIZE))
    
    # Clamp page to valid range
    page = max(1, min(page, total_pages))
    
    # Text fallback compilation
    table_text = build_squad_table(players, page, PAGE_SIZE)
    header = f"### 👥 SQUAD OVERVIEW — {club_name}\nPage {page} of {total_pages} ({total_players} players)\n\n"
    full_text = header + table_text
    
    # Build select menu options for players on this page
    start_idx = (page - 1) * PAGE_SIZE
    page_players = players[start_idx : start_idx + PAGE_SIZE]
    
    options = []
    for p in page_players:
        options.append({
            "label": p["display_name"],
            "value": p["id"],
            "description": f"{p['position']} | Age {p['age']} | OVR {p['overall']} | POT {p['potential']}"
        })
        
    select_custom_id = encode_custom_id("player", "view", "select", nonce)
    
    comp_payload = []
    
    if has_image:
        comp_payload.append(media_gallery(["attachment://squad.png"], ["Squad Overview Board"]))
    else:
        comp_payload.append(
            container([
                text_display(full_text)
            ])
        )
        
    # Add player select menu if options are available
    if options:
        player_select = select_menu(
            custom_id=select_custom_id,
            options=options,
            placeholder="🔍 Select a player to view details...",
            disabled=False
        )
        comp_payload.append(action_row([player_select]))
        
    # Navigation buttons
    prev_custom_id = encode_custom_id("squad", "page", str(page - 1), nonce)
    next_custom_id = encode_custom_id("squad", "page", str(page + 1), nonce)
    
    prev_btn = secondary_button("◀ Prev", prev_custom_id, disabled=(page <= 1))
    next_btn = secondary_button("Next ▶", next_custom_id, disabled=(page >= total_pages))
    
    comp_payload.append(action_row([
        prev_btn,
        next_btn,
        back_button("locker", nonce),
        refresh_button("squad", str(page), nonce),
        close_button(nonce)
    ]))
    
    return V2View(comp_payload)
