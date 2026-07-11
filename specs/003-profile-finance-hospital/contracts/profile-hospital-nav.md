# Contract: Profile ↔ Hospital navigation

## Surface

- **Existing**: `/store` → Club Facilities → Hospital Panel
- **New entry**: `/profile` → Manage Hospital → same panel with `origin="profile"`
- **Files**: `views/store_facilities.py`, `embeds/hospital_embeds.py`

## `show_hospital_panel` signature (conceptual)

```text
show_hospital_panel(interaction, owner_id, *, origin="facilities" | "profile")
```

Default `origin="facilities"` preserves current Store behavior.

## Back button

| origin | Back label (suggested) | Target |
|--------|------------------------|--------|
| `facilities` | Facilities (current) | `show_facilities` |
| `profile` | Profile / Club Dashboard | `show_profile` (full refresh) |

## Upgrade on panel

`HospitalPanelView` MUST expose Hospital upgrade (same RPC / gates as Facilities hub hospital upgrade):

- RPC: `upgrade_club_facility` with `p_facility_key='hospital'`
- Coins via existing facility upgrade path (`apply_club_economy` inside RPC)
- Weekly facility cooldown + match gates unchanged from 002
- After success: refresh hospital panel (same origin); when user Backs to profile, dashboard shows new level/coins

## Admit / discharge

Unchanged RPCs:

- `admit_to_hospital(p_owner_id, p_player_card_id)`
- `discharge_from_hospital(p_owner_id, p_player_card_id)`

After either: refresh panel with same `origin`.

## Data fetch (unchanged shape)

```text
players: select * where discord_id = owner_id
hospital_patients: select *, player_cards(...) where owner_id = owner_id and discharge_date is null
waiting: player_cards injured, in_hospital = false
```

## Guarantees

- Store → Facilities → Hospital → Back to Facilities still works (FR-014).
- Profile → Hospital → Back to Profile refreshes finance + hospital summary (FR-009).
- No `/hospital` slash command (FR-012).
