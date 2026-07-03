# app/ui/layouts/facility_upgrade.py

from datetime import datetime, timezone
from app.ui.components import container, text_display, action_row, primary_button, secondary_button, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button
from app.ui.formatters import format_money
from app.config import config

def build_facility_upgrade_layout(data: dict, nonce: str, success_message: str | None = None) -> V2View:
    """
    Builds the Facilities Upgrade Center layout.
    """
    budget_str = format_money(data["budget"])
    facilities = data.get("facilities", {})

    lines = []
    if success_message:
        lines.append(f"✅ {success_message}\n")

    lines.append("🛠️ **FACILITY UPGRADE CENTER**")
    lines.append(f"💰 **Club Budget:** `{budget_str}`\n")
    lines.append("Here is the status of your club's facilities. You can upgrade one facility at a time if you have enough budget:\n")

    facility_types = [
        ("stadium", "🏟️ Stadium"),
        ("training_pitch", "🏃 Training Pitch"),
        ("youth_academy", "🎓 Youth Academy"),
        ("medical_clinic", "🏥 Medical Clinic"),
        ("club_hq", "🏢 Club HQ")
    ]

    for f_type, display_name in facility_types:
        info = facilities.get(f_type, {"level": 1, "status": "IDLE", "upgrade_completes_at": None})
        level = info["level"]
        status = info["status"]

        status_str = ""
        cost_str = ""

        if status == "UPGRADING":
            status_str = "🛠️ *Upgrading*"
            if info.get("upgrade_completes_at"):
                try:
                    comp_dt = datetime.fromisoformat(info["upgrade_completes_at"])
                    now = datetime.utcnow().replace(tzinfo=timezone.utc)
                    if comp_dt > now:
                        diff = comp_dt - now
                        hours = int(diff.total_seconds() // 3600)
                        minutes = int((diff.total_seconds() % 3600) // 60)
                        status_str += f" ({hours}h {minutes}m remaining)"
                    else:
                        status_str += " (Pending completion)"
                except Exception:
                    pass
        elif status == "MAX_LEVEL":
            status_str = "⭐ *Max Level*"
        else:
            status_str = "🟢 *Idle*"

        if level >= config.FACILITY_MAX_LEVEL:
            cost_str = "Fully Upgraded"
        else:
            cost = config.FACILITY_UPGRADE_COSTS.get(level, 0)
            duration = config.FACILITY_UPGRADE_DURATIONS_HOURS.get(level, 0)
            cost_str = f"Cost: `{format_money(cost)}` (Duration: `{duration}h`)"
            if not info.get("manager_level_met", True):
                cost_str += f" | 🔒 **Locked** — requires Manager Level `{info.get('required_manager_level')}`"

        lines.append(f"**{display_name}** [Level {level}] — {status_str}")
        lines.append(f"└─ {cost_str}\n")

    lines.append("⚠️ *Note: Only one upgrade can be active across all facilities.*")
    text = "\n".join(lines)

    # Build upgrade buttons for each facility
    upgrade_buttons = []
    for f_type, display_name in facility_types:
        info = facilities.get(f_type, {"level": 1, "status": "IDLE"})
        # Custom ID for each upgrade button
        btn_id = encode_custom_id("facility", "upgrade", f_type, nonce)
        btn_label = display_name.split(" ")[1] # e.g. "Stadium", "Pitch", "Academy", "Clinic", "HQ"
        
        # Determine if disabled
        can_up = info.get("can_upgrade", True)
        is_disabled = (info["level"] >= config.FACILITY_MAX_LEVEL) or (info["status"] == "UPGRADING") or (not can_up)
        upgrade_buttons.append(primary_button(f"Upgrade {btn_label}", btn_id, disabled=is_disabled))

    back_id = encode_custom_id("locker", "open", "club", nonce)
    refresh_id = encode_custom_id("facility", "view", "upgrade_center", nonce)

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row(upgrade_buttons),
        action_row([
            secondary_button("◀ Back to Dashboard", back_id),
            secondary_button("🔄 Refresh", refresh_id),
            close_button(nonce)
        ])
    ]

    return V2View(comp_payload)
