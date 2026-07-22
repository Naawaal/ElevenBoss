# Quickstart: League Integrity (US-42.5)

## Validations

### 0 — Audit frozen
- [ ] `contracts/league-integrity-audit.md` Critical list matches plan W0

### 1 — Pause metadata
- [ ] Unreachable / bot-remove pause sets `pause_started_at`
- [ ] `resume_season` with null `pause_started_at` still fails closed (or backfill then resume)
- [ ] Pytest/source guard: pause helpers include `pause_started_at`

### 2 — Idempotency
- [ ] Double `_run_once` / operation key → second acquire False
- [ ] Prize key pattern `season_prize:` present in SQL
- [ ] `promo_applied` short-circuit present

### 3 — Play / absence
- [ ] Paused season → Play blocked; copy does **not** say Discord admin resume
- [ ] `is_played` fixtures skipped by deadline path
- [ ] Active match run skips auto-sim (existing)

### 4 — Seats / AI
- [ ] Soft Abandoned register still gated (076 / US-42.3)
- [ ] `distribute_season_prizes` humans-only (`is_ai = FALSE`)
- [ ] No member-leave club delete path

### 5 — Lock
- [ ] Spec Status → Locked after implement
- [ ] `change_log.md` if managers see new pause copy

## Smoke (optional)

```text
python -m pytest tests/test_league_integrity_pause.py -q
# if 078:
python scratch/apply_migration_078.py
python scratch/smoke_league_integrity_078.py
```
