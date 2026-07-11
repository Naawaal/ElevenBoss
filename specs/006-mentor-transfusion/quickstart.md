# Quickstart: Mentor Transfusion

**Feature**: `006-mentor-transfusion` | **Date**: 2026-07-11

Manual validation after implementation. Assumes migration `052` applied and `verify_required_schema.sql` passes.

## Prerequisites

- DB: `mentor_transfer_log` + `transfer_mentor_xp` present
- Bot deployed with Development mentor UI
- Test club with:
  - **Source**: `overall >= potential`, `skill_points >= 5` (ideally ≥ 15 for multi-unit tests)
  - **Target**: `overall < potential`, `level` well below 100, same `owner_id`
- Optional second maxed source for daily-cap tests

## Automated checks

```bash
pytest tests/test_mentor_math.py -q
```

Expect: conversion 5→1→500; eligibility predicates; `mentor_max_units` respects SP and XP headroom; invalid units rejected by preview helper.

## 1. Happy path (Development)

1. `/development` → **Allocate Skills** → select maxed source with SP ≥ 5.
2. **Expect**: Mentor Ready copy + **Mentor Transfer** (not a dead-end allocate-only screen).
3. Open Mentor Transfer → pick lower-level non-maxed target → choose **1 MP** → confirm preview (5 SP, 500 XP, level delta).
4. Confirm.
5. **Expect**: Source SP −5; target XP/level up; success shows transfers remaining (2 left if first of day).

## 2. Non-maxed regression

1. Allocate Skills on a non-maxed card with SP &gt; 0.
2. **Expect**: Six stat buttons; allocate still works; no Mentor Transfer required.

## 3. Insufficient SP

1. Maxed source with 1–4 SP.
2. **Expect**: Transfer unavailable / clear “need 5” copy; RPC would reject if forced.

## 4. Daily cap

1. Complete 3 successful transfers (any sources/targets) on the club today.
2. Attempt a 4th.
3. **Expect**: Clear daily-limit error; no SP/XP change ([transfer-mentor-xp-rpc.md](./contracts/transfer-mentor-xp-rpc.md)).

## 5. Near-ceiling target

1. Target with XP headroom &lt; 500 (or &lt; 1500 if testing 3 MP).
2. **Expect**: Amounts that would waste are disabled; Max equals headroom units; forcing oversized `N` via RPC rejects with no debit.

## 6. Profile Ready copy

1. Open player profile on maxed source with SP.
2. **Expect**: Mentor Ready + convertible MP/XP ([development-mentor-ui.md](./contracts/development-mentor-ui.md)).
3. Non-maxed profile: no mentor chrome.

## 7. Busy / cancel / double-tap

| Case | Expect |
|------|--------|
| Cancel on confirm | No writes |
| Double-tap Confirm | At most one success; second fails safely |
| Club in active match lock | Transfer blocked by match-lock middleware |
| Source injured | Transfer still allowed |

## 8. Unchanged systems smoke

| Flow | Expect |
|------|--------|
| Bot match complete | Match XP rates unchanged |
| `/store` claim / refill | Unchanged |
| Fusion | Still 3/day fusion log; independent of mentor 3/day |
| Marketplace list/buy | Prices unchanged |

## Schema verify

```bash
# after apply_migration_052
psql "$DATABASE_URL" -f supabase/scripts/verify_required_schema.sql
# or project scratch verify helper if used
```

## Ship checklist (abbrev)

- [ ] Migration applied + verify passes
- [ ] `tests/test_mentor_math.py` green
- [ ] Persona walkthrough: manager happy path, daily cap, non-maxed allocate unchanged
- [ ] `change_log.md` updated
- [ ] No new slash command; no `discord` in `packages/`
