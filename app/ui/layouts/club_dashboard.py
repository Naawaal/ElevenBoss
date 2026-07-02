from app.ui.components import container, text_display, action_row, primary_button, media_gallery, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button, back_button
from app.ui.formatters import format_money

def build_club_dashboard_layout(data: dict, nonce: str, has_image: bool = False) -> V2View:
    """
    Builds the Club Dashboard layout.
    """
    budget_str = format_money(data["budget"])
    stadium_capacity_formatted = f"{data['stadium_capacity']:,}"
    avg_ovr = data.get("average_overall", 0)
    filled_ovr = min(10, max(0, int(avg_ovr / 10)))
    ovr_bar = "▰" * filled_ovr + "▱" * (10 - filled_ovr)

    # Monospace ASCII Campus Map grid lines
    left_stadium = " STADIUM [Lv. 1]"
    right_training = " TRAINING PITCH [Lv. 1]"
    stadium_line = f"║{left_stadium:<26}║{right_training:<26}║"

    stadium_cap_label = f" Cap: {stadium_capacity_formatted}"
    training_pitch_label = " Standard Pitch"
    cap_line = f"║{stadium_cap_label:<26}║{training_pitch_label:<26}║"

    stadium_bar = " [███░░░░░░░]"
    training_bar = " [████░░░░░░]"
    bar_line_1 = f"║{stadium_bar:<26}║{training_bar:<26}║"

    left_academy = " YOUTH ACADEMY [Lv. 1]"
    right_clinic = " MEDICAL CLINIC [Lv. 1]"
    acad_clinic_line = f"║{left_academy:<26}║{right_clinic:<26}║"

    academy_desc = " Standard Academy"
    clinic_desc = " Standard Clinic"
    desc_line = f"║{academy_desc:<26}║{clinic_desc:<26}║"

    academy_bar = " [██░░░░░░░░]"
    clinic_bar = " [███░░░░░░░]"
    bar_line_2 = f"║{academy_bar:<26}║{clinic_bar:<26}║"

    offices_title = " CLUB HEADQUARTERS & OFFICES [Lv. 1]"
    offices_line_1 = f"║{offices_title:<53}║"

    offices_desc = " Standard HQ [█████░░░░░]"
    offices_line_2 = f"║{offices_desc:<53}║"

    text = (
        f"📊 **{data['club_name'].upper()} CAMPUS MAP**\n"
        f"👤 **Manager:** <@{data['discord_user_id']}>\n"
        f"💰 **Budget:** `{budget_str}`\n"
        f"🏆 **League Status:** `{data['league_status']}`\n"
        f"```yaml\n"
        f"╔══════════════════════════╦══════════════════════════╗\n"
        f"{stadium_line}\n"
        f"{cap_line}\n"
        f"{bar_line_1}\n"
        f"╠══════════════════════════╬══════════════════════════╣\n"
        f"{acad_clinic_line}\n"
        f"{desc_line}\n"
        f"{bar_line_2}\n"
        f"╠══════════════════════════╩══════════════════════════╣\n"
        f"{offices_line_1}\n"
        f"{offices_line_2}\n"
        f"╚═════════════════════════════════════════════════════╝\n"
        f"```\n"
        f"📈 **TEAM REPORT**\n"
        f"├─ 📈 **Team Rating:** `{avg_ovr}` OVR  {ovr_bar}\n"
        f"├─ 👥 **Squad Size:** `{data['squad_size']}` Players\n"
        f"├─ ⭐ **Star Player:** **{data['best_player_name']}** (`{data['best_player_ovr']}` OVR)\n"
        f"└─ 🔮 **Top Prospect:** **{data['highest_pot_name']}** (POT `{data['highest_pot_val']}`)\n\n"
        f"⭐ **Reputation:** `⭐⭐⭐` (3.0/5)"
    )
    
    squad_id = encode_custom_id("locker", "view", "squad", nonce)
    
    comp_payload = []
    if has_image:
        comp_payload.append(media_gallery(["attachment://club_dashboard.png"], ["Club Dashboard"]))
    else:
        comp_payload.append(
            container([
                text_display(text)
            ])
        )
        
    comp_payload.extend([
        action_row([
            primary_button("👥 View Squad", squad_id),
            refresh_button("locker", "club", nonce),
            back_button("locker", nonce),
            close_button(nonce)
        ])
    ])
    return V2View(comp_payload)
