# Contract: Hospital facility (Phase 2)

## Surface

- **Command**: existing `/store` → Club Facilities (no new slash command)
- **Files**: `store_facilities.py`, `hospital_embeds.py`, `facility_effects.py`

## Levels & effects

| Level | Beds | Recovery multiplier | Upgrade cost (from previous) |
|-------|------|---------------------|------------------------------|
| 0 | 1 | 1.00× | — |
| 1 | 2 | 0.83× | 1,500 |
| 2 | 3 | 0.71× | 4,000 |
| 3 | 4 | 0.625× | 10,000 |
| 4 | 5 | 0.55× | 25,000 |
| 5 | 6 | 0.50× | 60,000 |

`recovery_mult = 1 / (1 + 0.2 * level)` (display as “X% faster” from 1−mult).

## Upgrade RPC

Extend `upgrade_club_facility(p_owner_id, p_facility_key, p_expected_cost)`:

- Allow `p_facility_key = 'hospital'`
- Cost from `game_config.hospital_upgrade_costs[current_level]` (index 0 = cost to reach L1 from L0)
- Debit via `apply_club_economy(..., 'facility_upgrade')`
- Enforce shared `facility_last_upgrade_at` weekly cap
- Optional match gates: none required for L1; may add later — v1 can rely on cost + weekly cap only

**Must not**: `UPDATE players SET coins = coins - …` directly.

## Panel contents

- Level, beds used/max, recovery speed
- Active patients: name, tier, expected return
- Waiting (injured, not in hospital): actions Discharge other / Admit if bed frees / Leave untreated
- Upgrade button with cost + weekly cooldown reason

## Discharge / admit RPCs

- `discharge_from_hospital(p_owner_id, p_player_card_id)` — sets discharge_date; card continues untreated recovery at 1.0× remaining estimate (or keep expected date logic documented in tasks)
- `admit_to_hospital(p_owner_id, p_player_card_id)` — if bed free and card injured

## Gates elsewhere

| Location | Rule |
|----------|------|
| Squad XI | Reject injured cards |
| Development drills | Reject injured cards |
| Evolution start | Reject injured cards (recommended) |
| Fusion/sell | Block while `in_hospital` or injured (v1: block both) |

## Copy

Coins only; facility name **Medical Center** or **Hospital** (pick one label in `facility_label` — recommend **Hospital**).
