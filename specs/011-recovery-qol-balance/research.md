# Research: Recovery QoL Balance

**Feature**: `011-recovery-qol-balance` | **Date**: 2026-07-12  
**Purpose**: Resolve technical unknowns before implementation; map locked balance numbers onto existing pipes without new surface area.

---

## R1 — Mid-injury ETA handling

**Decision**: **Forward-only**. New injuries / new admits / overflow admits use bases **1/4/7**. Do not rewrite open `hospital_patients.expected_recovery_date` or `player_cards.injury_recovery_days` for cards already mid-injury.

**Rationale**:
- Spec Assumptions prefer not lengthening existing dates; optional shorten is allowed only if cheap.
- A one-time shorten needs careful hospital-level recompute and player messaging (“your ETA changed”) for little long-term value once the queue clears.
- Silent ETA jumps confuse managers who already planned around the old date.

**Alternatives considered**:

| Option | Rejected because |
|--------|------------------|
| One-time shorten open stays to new bases | Extra SQL + support edge cases; not required for SC-001/002 |
| Clamp all ETAs to ≤7 days remaining | Arbitrary vs Hospital curve; can surprise managers |

---

## R2 — Injury base storage (config vs CASE)

**Decision**: Keep injury bases as **SQL `CASE` + Python `BASE_RECOVERY_DAYS`**. Do **not** add `game_config` keys for Minor/Moderate/Major days in this patch.

**Rationale**:
- Current production path (migration `050`) never put injury bases in `game_config`; fatigue drain/bench/passive already do.
- Adding three config keys requires REPLACE of both admit RPCs *and* a bot/ops convention nobody uses yet — more surface for a one-time retune.
- Spec FR-007 is satisfied by updating the existing dual source of truth (RPC CASE + `injury_math.py`).

**Alternatives considered**:

| Option | Rejected because |
|--------|------------------|
| `injury_base_days_minor/moderate/major` in `game_config` | Nice for ops, YAGNI for this QoL patch; can revisit if ops need live tuning |
| Python-only change | Live admits use SQL CASE — Python alone would desync ETAs |

---

## R3 — Where each lever actually applies

| Lever | Live write path | Must change |
|-------|-----------------|-------------|
| Base drain **18** | Python `match_fatigue_drain` → JSONB into `apply_match_fatigue` | `FATIGUE_BASE_DRAIN` (+ seed `game_config.fatigue_base_drain` for ops parity) |
| Bench **+25** | SQL `apply_match_fatigue` via `get_game_config_int('fatigue_bench_per_match')` | Upsert config; mirror `FATIGUE_BENCH_PER_MATCH` |
| Passive base **25** | SQL `process_daily_recovery` via `fatigue_passive_base` | Upsert config; mirror `FATIGUE_PASSIVE_BASE`; update RPC fallback default if REPLACE |
| Injury **1/4/7** | SQL `process_post_match_injuries` + `admit_to_hospital` CASE | REPLACE both; mirror `BASE_RECOVERY_DAYS` |

**Decision**: Migration upserts the three fatigue config keys; replaces only the two injury RPCs for CASE. No need to REPLACE `apply_match_fatigue` solely for bench if upsert lands first (fallback 15 only matters if key missing). Prefer still bumping the fallback to 25 if that function is touched for any reason; otherwise leave body alone (ponytail).

---

## R4 — Drain example / tests

**Decision**: Update the documented GDD-style example in `match_fatigue_drain` and `test_drain_gdd_example`:

- Old: PHY 70, Attack, intensity → `22 - 10.5 + 8 + 5 = 24.5 → 25`
- New: same modifiers → `18 - 10.5 + 8 + 5 = 20.5 → 21`

Hospital recovery day asserts: Minor untreated → **1**; Moderate @ Hospital L3 → `ceil(4 / 1.6) = 3` (was 5 from base 8).

Passive: TG1 → **30**, TG3 → **40**, TG5 → **50**.

---

## R5 — Product research (already locked in spec)

Industry takeaways (Top Eleven short real clocks; EA FC in-game days; FM large-squad tolerance) justify **compression of real-day clocks**, not monetized instant-heal consumables. Spec Out of Scope already excludes Store “Rests” / Rest toggles — no further research needed for implement.

---

## Spec reconcile on implement

- `.specify/specs/v1.0.0/spec.md` **AC-39h**: passive `15+TG×5` / bench +15 → `25+TG×5` / bench +25; document injury bases 1/4/7 and drain 18.
- `change_log.md`: replace TG passive / bench lines under Fatigue & Recovery Session sections.
- Feature `009` docs stay historical; do not rewrite completed 009 tasks.
