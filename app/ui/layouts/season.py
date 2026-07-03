from app.ui.components import container, text_display, action_row, V2View
from app.ui.layouts.common import back_button, close_button

def build_season_summary_layout(snapshot_data: dict, nonce: str) -> V2View:
    """
    Builds a retro text-based season summary display using Discord Components V2.
    """
    champ = snapshot_data.get("champion_name") or "N/A"
    runner_up = snapshot_data.get("runner_up_name") or "N/A"
    season_number = snapshot_data.get("season_number") or 1
    total_matches = snapshot_data.get("total_matches") or 0
    total_goals = snapshot_data.get("total_goals") or 0

    table_rows = snapshot_data.get("table_rows", [])
    
    # Standings ASCII table representation inside the monospace box
    # Column sizes: Rank (2), Club (14), P (2), W (2), D (2), L (2), GD (3), PTS (3)
    ascii_table = (
        "╔══╦═══════════════╦══╦══╦══╦══╦═══╦═══╗\n"
        "║R ║ CLUB          ║P ║W ║D ║L ║GD ║PTS║\n"
        "╠══╬═══════════════╬══╬══╬══╬══╬═══╬═══╣\n"
    )
    for r in table_rows:
        club_name = r.get("club_name") or "Club"
        gd = r.get("goal_difference", r.get("goals_for", 0) - r.get("goals_against", 0))
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        
        ascii_table += (
            f"║{r.get('rank'):<2}║ {club_name:<14}║{r.get('played'):<2}║{r.get('wins'):<2}║"
            f"{r.get('draws'):<2}║{r.get('losses'):<2}║{gd_str:<3}║{r.get('points'):<3}║\n"
        )
    ascii_table += "╚══╩═══════════════╩══╩══╩══╩══╩═══╩═══╝"

    text = (
        f"🏆 **SEASON {season_number} SUMMARY & ARCHIVE**\n"
        f"────────────────────────────────────────\n"
        f"🥇 **Champion:** **{champ}**\n"
        f"🥈 **Runner-up:** **{runner_up}**\n\n"
        f"📊 **SEASON STATISTICS**\n"
        f"├─ 📅 **Total Matches Played:** `{total_matches}`\n"
        f"└─ ⚽ **Total Goals Scored:** `{total_goals}`\n\n"
        f"🏁 **FINAL STANDINGS TABLE**\n"
        f"```yaml\n"
        f"{ascii_table}\n"
        f"```"
    )

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            back_button("locker", nonce),
            close_button(nonce)
        ])
    ]

    return V2View(comp_payload)
