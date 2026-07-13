# Contract: Manage Academy UI

**Feature**: `015-youth-academy`  
**Entry**: `/profile` → **Manage Academy**  
**No new slash command**

## Surfaces

### Profile hub (entry)

- **Manage Academy** button on `/profile` (alongside Manage Hospital).

### Club Facilities embed (delta)

- Youth Academy field shows: level, slot used/cap, growth blurb; points managers to `/profile` → Manage Academy.
- Buttons: Upgrade YA / Upgrade TG / Back only (no Manage Academy).

### Manage Academy hub embed

| Block | Content |
|-------|---------|
| Header | Club name · YA Lx · Slots `used/cap` · Coins |
| Help | One-liner: weekly intake → grow → promote/release · paid scout optional |
| Next intake | Days until next Monday UTC (or “due Monday”) |
| Scout status | Idle / finishes_at / report ready |
| Prospect list | Up to cap lines: pos · name · age · OVR · ⭐band · progress bar toward next OVR · `Ready` badge if OVR ≥ ready |

### Actions (buttons / selects)

| Control | Behavior |
|---------|----------|
| Select prospect | Enable Promote / Release |
| Promote | Confirm → `promote_academy_player` → refresh; early-promote warning if below ready |
| Release | Confirm destructive → `release_academy_player` |
| Scout… | Tier buttons → `dispatch_youth_scout` |
| Claim report | Show shortlist (fog by tier) → Sign one |
| Back | Facilities hub |

### DMs

- Intake DM: “Seated in academy” + Manage Academy path; mention skips.
- Scout ready DM: optional; hub remains source of truth (FR-011).
- Age-out DM: promoted or released copy.

## Exclusions elsewhere

| Surface | Rule |
|---------|------|
| `/squad` assign | Reject `in_academy` with clear ephemeral |
| Full roster | Prefer hide academy or separate section — **v1: exclude from senior sell/drill pickers; academy list only in Manage Academy** |
| Marketplace sell | Exclude `in_academy` |
| Development targets | Exclude `in_academy` |

## Interaction rules

- Defer on every button before RPC.
- Owner-only `interaction_check`.
- Double-tap: rely on RPC guards; re-render hub after success.
