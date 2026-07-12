# Contract: Store facilities without Hospital

**Feature**: `010-recovery-energy-cleanup`  
**File**: `apps/discord_bot/views/store_facilities.py`

## Facilities hub (`facilities_embed` + `FacilitiesHubView`)

**Remove**:
- Hospital level field
- `⬆️ Upgrade Hospital` button
- `🏥 Hospital Panel` button
- Description/footer text that lists Hospital as a Store-upgradable facility or “open Hospital panel”

**Keep**:
- Youth Academy + Training Ground fields and upgrade buttons
- Weekly facility cooldown messaging for YA/TG only
- `show_hospital_panel`, `HospitalPanelView`, hospital upgrade helpers (Profile still calls them with `origin="profile"`)

## Profile

`profile_cog.Manage Hospital` → `show_hospital_panel(..., origin="profile")` unchanged.
