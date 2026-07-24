# Data Model: Store / Swap / Hospital UX Refinements

**Feature**: `042-ux-visual-refinements` | **Date**: 2026-07-23

No database schema changes. Entities below are **view/render models** derived from existing tables/RPCs.

## ActionEnergyBalance

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `current` | int ≥ 0 | `sync_action_energy` → `action_energy` | Club action energy after sync |
| `maximum` | int > 0 | `sync_action_energy` → `max_energy` | Default 120 if absent in UI only after fail-open check |
| `near_full` | bool | derived | See validation |
| `reason` | `full` \| `near` \| `null` | derived | Drives button label + copy |

**Validation / derivation**

- If `maximum` is missing or `≤ 0`: `near_full = false`, `reason = null` (fail-open).
- Else if `current >= maximum`: `reason = full`.
- Else if `current >= ceil(0.95 * maximum)` **or** `current >= maximum - 5`: `reason = near`.
- Else: `reason = null`.
- `near_full = reason is not null`.

**State transitions (UI only)**

```text
[below threshold] --store refresh / energy spend--> [near|full]  (button disabled)
[near|full] --energy drops below threshold--> [below]           (button enabled)
```

## SwapPair

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `out_card` | CardSnapshot \| null | Selected starter from XI | Null until select |
| `in_card` | CardSnapshot \| null | Selected eligible reserve | Null until select |
| `confirm_ready` | bool | `_swap_selection_ready` | Unchanged |
| `eligible_reserves` | list | Existing `_eligible_reserves` | Unchanged |

### CardSnapshot (render input)

| Field | Required | Notes |
|-------|----------|-------|
| `id`, `name`, `position`, `overall` | yes | Always used on compare image |
| `rarity`, `level` | optional | Border / footer if present |
| `pac`, `sho`, `pas`, `dri`, `def`, `phy` (or existing attr keys) | optional | Show when available; omit row if absent |

**Validation**: Visual must never imply confirm when `confirm_ready` is false. Placeholders when either card is null.

## HospitalOccupancy

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `patients` | list[PatientRow] | `hospital_patients` where `discharge_date` is null | Admitted |
| `waiting` | list[WaitingRow] | injured cards `in_hospital = false` | Text field only |
| `bed_capacity` | int | `hospital_bed_capacity(hospital_level)` | Existing |
| `visual_slots` | int = 6 | Design constant | Cap overlays |
| `overlay_patients` | list | `patients[:visual_slots]` | Drawn on board |
| `overflow_patients` | list | `patients[visual_slots:]` | Text only |

### PatientRow (overlay)

| Field | Notes |
|-------|-------|
| `name` | From nested `player_cards` or row |
| `injury_tier` / severity label | Optional short suffix on row |
| `expected_recovery_date` | Prefer keep full ETA in embed text; optional short on image |

**State**: Each `show_hospital_panel` rebuilds occupancy from DB → new image bytes → no client cache.

## HospitalVisualAsset

| Field | Value |
|-------|-------|
| Path | `assets/admited.png` |
| Size | 1536×1024 |
| Role | Clipboard/list board base; lined rows ≈ 5–6 patient lines |
| Missing behavior | Generator returns `None`; embed text-only |

## Relationships

```text
ActionEnergyBalance ----drives----> StoreHubView.refill_button.enabled/label
SwapPair.out/in --------drives----> swap_compare.png attachment
HospitalOccupancy ------drives----> hospital_board.png + embed patient fields
```
