# Data Model: Recovery QoL Balance

**Feature**: `011-recovery-qol-balance`  
**Schema impact**: **None** (no new tables/columns). Config value + formula constant changes only.

---

## Entities (unchanged shape)

| Entity | Role in this feature |
|--------|----------------------|
| `game_config` | Runtime ints for fatigue drain/bench/passive base |
| `player_cards.fatigue` | Still 0–100; clamp unchanged |
| `player_cards.injury_tier` / `injury_recovery_days` / `in_hospital` | New admits use shorter day bases |
| `hospital_patients.expected_recovery_date` | Computed from new bases on insert only |
| Training Ground / Hospital facility levels | Multipliers unchanged |

---

## `game_config` retunes

| Key | Before | After | Consumers |
|-----|--------|-------|-----------|
| `fatigue_passive_base` | `15` | `25` | `process_daily_recovery` |
| `fatigue_passive_tg_per_level` | `5` | `5` (unchanged) | same |
| `fatigue_bench_per_match` | `15` | `25` | `apply_match_fatigue` |
| `fatigue_base_drain` | `22` | `18` | Ops/docs mirror; **bot uses Python constant** |
| `fatigue_hospital_per_day` | `45` | unchanged | hospital daily fatigue |
| `fatigue_recovery_session` / `fatigue_recovery_energy` | 40 / 5 | unchanged | Recovery Session |

Passive effective table after patch:

| TG level | Daily bump |
|----------|------------|
| 1 | 30 |
| 2 | 35 |
| 3 | 40 |
| 4 | 45 |
| 5 | 50 |

---

## Injury base days

| Tier | Before | After | Hospital shortening |
|------|--------|-------|---------------------|
| 1 Minor | 3 | **1** | `ceil(base / (1 + 0.2 × H))`, min 1 |
| 2 Moderate | 8 | **4** | same formula |
| 3 Major | 20 | **7** | same formula |

Example Hospital L5 Major: `ceil(7 / 2.0) = 4` days (was `ceil(20/2)=10`).

**Open stays**: not rewritten (forward-only).

---

## Python mirrors (`packages/player_engine`)

| Constant / map | New value |
|----------------|-----------|
| `FATIGUE_BASE_DRAIN` | 18 |
| `FATIGUE_PASSIVE_BASE` | 25 |
| `FATIGUE_PASSIVE_TG_PER_LEVEL` | 5 |
| `FATIGUE_BENCH_PER_MATCH` | 25 |
| `BASE_RECOVERY_DAYS` | `{1: 1, 2: 4, 3: 7}` |
| Deprecated alias `FATIGUE_PASSIVE_PER_DAY` | `25+5=30` (TG1 floor) |

---

## Validation / guards (migration end)

Assert after upsert:

- `get_game_config_int('fatigue_passive_base', 0) = 25`
- `get_game_config_int('fatigue_bench_per_match', 0) = 25`
- `get_game_config_int('fatigue_base_drain', 0) = 18`
- Existing function presence guards for `process_post_match_injuries`, `admit_to_hospital` (already in `verify_required_schema.sql`)
