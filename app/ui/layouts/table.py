from app.ui.components import container, text_display, action_row, secondary_button, success_button, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button

def build_table_layout(data, nonce: str) -> V2View:
    """
    Builds the Standings Table UI using Discord Components V2.
    """
    text = "### 📊 LEAGUE STANDINGS\n"
    
    # Render table header
    # Pos Club              P  W  D  L  GF GA  GD PTS
    header = f"{'#':<3} {'Club':<16} {'P':>2} {'W':>2} {'D':>2} {'L':>2} {'GF':>3} {'GA':>3} {'GD':>3} {'PTS':>3}\n"
    divider = "─" * 48 + "\n"
    
    table_rows = ""
    for row in data:
        # Pad club name up to 16 characters
        club_name = f"{row.club_name:<16}"[:16]
        gd_val = row.goal_difference
        gd_str = f"{gd_val:+d}" if gd_val > 0 else f"{gd_val}"
        
        table_rows += (
            f"{row.rank:<3} {club_name} "
            f"{row.played:>2} {row.wins:>2} {row.draws:>2} {row.losses:>2} "
            f"{row.goals_for:>3} {row.goals_against:>3} {gd_str:>3} {row.points:>3}\n"
        )
        
    table_str = f"```text\n{header}{divider}{table_rows}```"
    text += table_str
    
    # Custom IDs
    refresh_id = encode_custom_id("table", "refresh", "main", nonce)
    back_league_id = encode_custom_id("nav", "back", "league", nonce)
    back_locker_id = encode_custom_id("nav", "back", "locker", nonce)
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            secondary_button("🔄 Refresh", refresh_id),
            secondary_button("🏆 League", back_league_id),
            secondary_button("🏟️ Locker Room", back_locker_id),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)
