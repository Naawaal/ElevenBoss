# Data Model: Profile Finance & Hospital Hub

**Feature**: `003-profile-finance-hospital` | **Date**: 2026-07-11

This feature introduces **no new persisted tables or columns**. It defines a **read model** for the `/profile` dashboard and navigation state for hub views.

## Persisted entities (existing — read)

### Club wallet (`players`)

| Field | Source | Profile use |
|-------|--------|-------------|
| `discord_id` | PK | Owner key |
| `club_name`, `manager_name` | columns | Title / identity |
| `coins` | BIGINT | Finance section |
| `tokens` | INT | Gems in UI |
| `action_energy` / sync RPC | energy | Existing energy field |
| `hospital_level` | 0–5 | Hospital section |
| `youth_academy_level`, `training_ground_level` | facilities | Finances detail only |
| `wins` / `draws` / `losses` / `matches_played` | record | Existing match record |
| `division`, `league_points`, `global_lp`, … | league | Existing sections |
| `facility_last_upgrade_at` | timestamptz | Upgrade eligibility inside hospital panel (not summary) |

### Active hospital patient (`hospital_patients` + `player_cards`)

| Field | Rule for profile summary |
|-------|--------------------------|
| `owner_id` | Must equal manager `discord_id` |
| `discharge_date IS NULL` | Active bed only |
| `expected_recovery_date` | Show as return date |
| `injury_tier` | Optional severity label |
| `player_cards.name` | Display name |

**Bed usage**: `occupied = count(active patients)`; `capacity = hospital_bed_capacity(hospital_level)` from `economy.facility_effects` (**not** shown on profile when level is 0 — see view rules).

### Finance detail extras (Finances button / `/club-finances`)

| Input | Use |
|-------|-----|
| `squad_assignments` → `player_cards(*)` | Starting XI for `calculate_weekly_wages` |
| Facility levels on `players` | YA / TG / Hospital line |

## View entities (ephemeral — not stored)

### Club Profile Dashboard

Composite Discord embed + `ProfileHubView`.

| Section | Required content |
|---------|------------------|
| Identity | Club name, manager, username |
| Club Finance | Coins, gems (tokens); optional light visual cue |
| Hospital | See state machine below |
| Energy / Division / Record / Trophies | Existing `/profile` fields retained |
| Actions | Manage Hospital, Finances, View Club Stats |

### Hospital summary states

```text
hospital_level == 0
  → empty state copy (FR-004); no bed fraction; CTA toward Store / Manage Hospital upgrade

hospital_level >= 1 AND occupied == 0
  → Level · Beds 0/N · Recovery mult · “No injuries”

hospital_level >= 1 AND occupied > 0
  → Level · Beds occupied/N · Recovery mult · patient lines (truncated)

patients query failed
  → Finance + core profile still render; Hospital = “Hospital status unavailable”
```

### Profile navigation origin

| Value | Back from hospital panel |
|-------|--------------------------|
| `facilities` | `show_facilities` (Store path) |
| `profile` | `show_profile` (refresh dashboard) |

Not persisted — held on the `View` instance for the message lifetime.

## Validation rules (UI)

- Patient summary lines capped (~5); overflow → “and N more — open Manage Hospital”.
- Gems display `0` when `tokens` is 0 (consistent wallet).
- Owner-only `interaction_check` on all profile-originated views.
- No writes from dashboard render path.

## Relationships

```text
players
  ├── coins / tokens          → Finance summary + Finances panel
  ├── hospital_level          → Hospital summary + panel
  ├── hospital_patients[]     → bed occupancy + patient list (active only)
  └── squad_assignments[]     → Finances wage forecast only

ProfileHubView
  ├──→ HospitalPanelView (origin=profile)
  ├──→ ClubFinancesPanelView → Back → show_profile
  └──→ SquadHubView (edit-in-place)
```

## Out of model (v1)

- Ledger rows / recent income-expense feed
- New hospital or finance tables
- Cached dashboard snapshots
