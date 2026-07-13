# Quickstart: Youth Academy Workflow Validation

**Feature**: `015-youth-academy`  
**Date**: 2026-07-12

## Prerequisites

- Migration `060_youth_academy_workflow.sql` applied
- `supabase/scripts/verify_required_schema.sql` passes (or migration guard)
- Bot running with scheduler (or manual RPC invoke for growth)
- Test human club with coins and known `youth_academy_level`

## 1. Pure math (no Discord)

```bash
pytest tests/test_youth_math.py tests/test_academy_slots.py -q
```

Expect: L5 points &gt; L1; OVR never exceeds POT; slot caps 4/5/6/8/10; ready at 65.

## 2. Schema

```bash
python scratch/apply_migration_060.py
python scratch/verify_schema_full.py
# or: psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

Expect: `in_academy`, `scouting_reports`, listed RPCs present.

## 3. Manage Academy entry (US1)

1. `/profile`  
2. Confirm **Manage Academy** button  
3. Open hub — see level, slots `0/N` or current, help copy, next intake hint  

## 4. Intake seating (US2)

1. With free slots, run intake job or RPC with generated cards  
2. Manage Academy lists new prospects; `/squad` cannot assign them  
3. Fill academy to cap; run intake again — `skipped > 0`, existing prospects unchanged  

## 5. Growth (US3)

1. Note `overall` + `academy_progress`  
2. Invoke `process_daily_academy_growth` (or wait for cron)  
3. Progress increased; after enough ticks OVR +1 and ≤ POT  

## 6. Promote / release (US4–US5)

1. Promote with senior count &lt; cap → appears in senior roster pickers; `in_academy=false`  
2. Fill senior to cap → promote errors with actionable copy  
3. Release another academy card → slot frees  

## 7. Scouting (US6)

1. Dispatch `quick` with enough coins → timer set, coins down  
2. Fast-forward / set `scouting_finishes_at` past → finalize report  
3. Sign one prospect into free slot; second sign rejected  
4. Full academy → sign blocked; report still visible until expiry  

## 8. Persona unhappy paths

- DMs disabled: intake still visible in Manage Academy  
- Double-tap promote/scout: no duplicate card / no double charge  
- Stale embed: refresh hub after action  

## Done when

- [ ] P1 scenarios 3–6 pass on a test club (code wired; run live Discord smoke)  
- [ ] P2 scenario 7 passes (code wired; run live Discord smoke)  
- [x] pytest green  
- [x] Schema verify green (`060` guard / verify_required_schema)  
- [x] `change_log.md` updated on ship  
