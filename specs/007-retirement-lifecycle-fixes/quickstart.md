# Quickstart: Retirement Lifecycle Fixes

**Feature**: `007-retirement-lifecycle-fixes` | **Date**: 2026-07-11

Manual validation after implementation. Assumes migration `053` applied and `verify_required_schema.sql` passes (`players.squad_invalid` present).

## Prerequisites

- DB: updated `retire_player_card`, `process_season_aging`, `set_formation_and_assignments`
- Bot with battle gate copy
- Test club with: full starting XI, ≥1 reserve matching a starter’s slot role, and a separate scenario with no matching reserve

## Automated checks

```bash
pytest tests/test_age_manager.py tests/test_regen_pool.py -q
```

Expect:

- `yearly_stat_decline(33)` includes `dri: -1` (and pas/def)
- `yearly_stat_decline(35)` includes `sho: -1` and `dri: -1`
- Regen rarity samples for ≥85 / 80–84 / 75–79 match [regen-rarity-weights.md](./contracts/regen-rarity-weights.md)

## 1. Decline curve (math)

1. Call or unit-test `yearly_stat_decline` for ages 31, 33, 35.
2. **Expect**: table in [aging-decline-curve.md](./contracts/aging-decline-curve.md).

Optional SQL smoke: age a card across a birthday boundary in a transaction and confirm `dri`/`sho` dropped.

## 2. Auto-promote on retire

1. Put a DEF in starting slot that requires DEF; leave another DEF on reserve (not in XI).
2. Force-retire the starter (RPC `retire_player_card` or age batch).
3. **Expect**: vacated slot filled by the reserve; `squad_invalid` false; club still has 11 assignments ([retire-squad-vacancy-rpc.md](./contracts/retire-squad-vacancy-rpc.md)).

## 3. Squad hole + match block

1. Retire a starter with **no** same-role reserve.
2. **Expect**: slot empty; `players.squad_invalid = true`.
3. `/battle` bot (or league/friendly start).
4. **Expect**: ephemeral block with retirement + `/squad` guidance ([battle-squad-invalid-gate.md](./contracts/battle-squad-invalid-gate.md)); no match started.

## 4. Repair via `/squad`

1. From invalid club, open `/squad`, assign a full valid XI, save.
2. **Expect**: `squad_invalid = false`.
3. Start bot match again → allowed (energy/other gates permitting).

## 5. Regen rarity fantasy

1. Generate many regens from a synthetic retired card with `overall=88` (seeded RNG in unit tests).
2. **Expect**: only Rare/Epic; ~50/50.
3. Repeat for 82 and 77 → weights per contract.

## 6. Regression

- Card below 31: no decline.
- Bench-only retirement: no `squad_invalid` from that retire alone.
- Already-retired card: second retire raises / no-ops safely.
- Regen below OVR 75: no scouting listing (existing job gate).

## Done when

- [ ] Migration 053 + verify pass
- [ ] Pytest age + regen green
- [ ] Auto-promote and invalid-gate manual paths verified
- [ ] `change_log.md` notes the three fixes
- [ ] `.specify/specs/v1.0.0` AC-31d / regen notes reconciled
