# Quickstart: Youth Academy Rarity-Cap Redesign

**Feature**: `051-youth-academy-rarity`  
**Purpose**: Runnable validation after migration **095** + bot wiring. Not an implementation guide.

## Prerequisites

- `DATABASE_URL` / Supabase project with migrations through **095** applied
- `python scratch/verify_schema_full.py` or `psql … -f supabase/scripts/verify_required_schema.sql` passes (includes new YA V2 guards)
- Bot build with `youth_academy_v2_enabled` readable from `game_config`
- pytest env for pure packages

## 1. Pure math / unit

```bash
pytest tests/test_academy_slots.py tests/test_youth_math.py tests/test_youth_intake_v2.py tests/test_scout_ranges.py tests/test_academy_weekly_ledger.py -q
```

**Expect**: caps 3/3/4/4/5; every generated sample obeys rarity ceilings; range narrows monotonically and always contains true POT; Legendary weight 0 below L5 and when kill switch on.

## 2. Schema / RPC smoke

1. Apply `095_youth_academy_rarity_v2.sql` via project scratch apply script.
2. Verify schema script green.
3. On a clone club: run cutover repair; confirm illegal-but-repairable academy POT fixed without lowering legal OVR; over-cap club still has all seats; `pot_visible_*` contain POT.

## 3. Intake capacity

| Setup | Action | Expect |
|-------|--------|--------|
| 0 occupied, L1 (cap 3) | Monday intake once | ≤2 seated; log row for week |
| Same week retry | intake job | 0 new seats |
| Full academy | intake | 0 seated; capacity_blocked signal |
| Over-cap grandfather (e.g. 5/3) | intake / discovery sign | blocked until promote/release down |

## 4. Scout assessment UX

1. Open `/development` → Youth Academy (primary).
2. New prospect shows **range**, not exact POT; stars match interval.
3. Run Quick → Standard → Deep: range only narrows; Deep ≠ exact POT default.
4. Double-dispatch same prospect: second rejected, no double charge.

## 5. Promote ledger + graduation

1. Promote twice in one UTC week → both succeed (fee rules per config); graduation embed shows milestone fields.
2. Third promote → blocked with clear copy.
3. Full senior soft-cap → promote fails; prospect remains in academy.

## 6. Facilities preview

`/store` → Club Facilities → Youth upgrade preview shows numeric before→after for capacity, rarity odds, range width, growth speed. After upgrade, existing prospects’ rarity/POT unchanged.

## 7. Aging (staging clock / SQL fixture)

Advance a fixture prospect through warn → decay ≤1 POT → pending → grace expiry → **auto-release** (not forced senior, not silent without pending state).

## 8. Rollback / flag

With `youth_academy_v2_enabled = false`, document expected degraded path (emergency only). Legendary kill switch alone must zero L5 Legendary without disabling other rarities.

## Pass criteria

Map results to success criteria SC-001…SC-010 in [spec.md](./spec.md). Ship bot paths only after schema verify + P0/P1 unit green.
