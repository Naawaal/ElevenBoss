# app/ui/layouts/club_dashboard.py

from datetime import datetime, timezone
from app.ui.components import container, text_display, action_row, primary_button, media_gallery, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button, back_button
from app.ui.formatters import format_money
from app.config import config

def build_club_dashboard_layout(data: dict, nonce: str, has_image: bool = False) -> V2View:
    """
    Builds the Club Dashboard layout.
    """
    budget_str = format_money(data["budget"])
    stadium_capacity_formatted = f"{data['stadium_capacity']:,}"
    avg_ovr = data.get("average_overall", 0)
    filled_ovr = min(10, max(0, int(avg_ovr / 10)))
    ovr_bar = "▰" * filled_ovr + "▱" * (10 - filled_ovr)

    facilities = data.get("facilities", {})

    def get_fac_info(f_type: str):
        info = facilities.get(f_type, {"level": 1, "status": "IDLE", "upgrade_completes_at": None})
        lvl = info["level"]
        status = info["status"]
        return lvl, status, info

    std_lvl, std_status, std_info = get_fac_info("stadium")
    pt_lvl, pt_status, pt_info = get_fac_info("training_pitch")
    ya_lvl, ya_status, ya_info = get_fac_info("youth_academy")
    mc_lvl, mc_status, mc_info = get_fac_info("medical_clinic")
    hq_lvl, hq_status, hq_info = get_fac_info("club_hq")

    def get_progress_bar(level: int, status: str, info: dict, name: str) -> str:
        if status == "UPGRADING" and info.get("upgrade_completes_at"):
            try:
                comp_dt = datetime.fromisoformat(info["upgrade_completes_at"])
                now = datetime.utcnow().replace(tzinfo=timezone.utc)
                if comp_dt > now:
                    diff = comp_dt - now
                    hours = int(diff.total_seconds() // 3600)
                    minutes = int((diff.total_seconds() % 3600) // 60)
                    return f" 🛠️ {hours}h {minutes}m left"
                else:
                    return " 🛠️ Pending completion"
            except Exception:
                return " 🛠️ Upgrading..."
        elif status == "MAX_LEVEL":
            return " [██████████] MAX"
        else:
            filled = level * 2
            bar = "█" * filled + "░" * (10 - filled)
            return f" [{bar}]"

    # Lines construction
    stadium_title = f" STADIUM [Lv. {std_lvl}]"
    if std_status == "UPGRADING":
        stadium_title += " 🛠️"
    training_title = f" TRAINING PITCH [Lv. {pt_lvl}]"
    if pt_status == "UPGRADING":
        training_title += " 🛠️"
    
    stadium_line = f"║{stadium_title:<26}║{training_title:<26}║"

    stadium_cap_label = f" Cap: {stadium_capacity_formatted}"
    pt_bonus = config.TRAINING_PITCH_RECOVERY_BONUS.get(pt_lvl, 0)
    training_pitch_label = f" Recovery Bonus: +{pt_bonus}"
    cap_line = f"║{stadium_cap_label:<26}║{training_pitch_label:<26}║"

    stadium_bar = get_progress_bar(std_lvl, std_status, std_info, "stadium")
    training_bar = get_progress_bar(pt_lvl, pt_status, pt_info, "training_pitch")
    bar_line_1 = f"║{stadium_bar:<26}║{training_bar:<26}║"

    academy_title = f" YOUTH ACADEMY [Lv. {ya_lvl}]"
    if ya_status == "UPGRADING":
        academy_title += " 🛠️"
    clinic_title = f" MEDICAL CLINIC [Lv. {mc_lvl}]"
    if mc_status == "UPGRADING":
        clinic_title += " 🛠️"
    acad_clinic_line = f"║{academy_title:<26}║{clinic_title:<26}║"

    academy_desc = f" Academy Level {ya_lvl}"
    mc_bonus = config.MEDICAL_CLINIC_INJURY_RECOVERY_BONUS.get(mc_lvl, 0)
    clinic_desc = f" Recovery Bonus: +{mc_bonus}"
    desc_line = f"║{academy_desc:<26}║{clinic_desc:<26}║"

    academy_bar = get_progress_bar(ya_lvl, ya_status, ya_info, "youth_academy")
    clinic_bar = get_progress_bar(mc_lvl, mc_status, mc_info, "medical_clinic")
    bar_line_2 = f"║{academy_bar:<26}║{clinic_bar:<26}║"

    offices_title = f" CLUB HEADQUARTERS & OFFICES [Lv. {hq_lvl}]"
    if hq_status == "UPGRADING":
        offices_title += " 🛠️"
    offices_line_1 = f"║{offices_title:<53}║"

    hq_bar = get_progress_bar(hq_lvl, hq_status, hq_info, "club_hq")
    offices_desc = f" HQ Level {hq_lvl}{hq_bar}"
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
    upgrade_center_id = encode_custom_id("facility", "view", "upgrade_center", nonce)
    
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
            primary_button("🛠️ Upgrade", upgrade_center_id),
            refresh_button("locker", "club", nonce),
            back_button("locker", nonce),
            close_button(nonce)
        ])
    ])
    return V2View(comp_payload)
