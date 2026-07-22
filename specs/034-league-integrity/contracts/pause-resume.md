# Contract: Pause & Resume

**Feature**: US-42.5 | Aligns `026` rebase rules

## Pause entry

Triggers: guild unreachable (confirmed), bot removed from guild, ops/internal pause.

Writes (atomic intent):

1. `status = 'paused'`
2. `pause_started_at = NOW()` if not already paused (do not reset clock on redundant pause)
3. Optional reason in logs / future column — not required for MVP

Eligible prior statuses: non-terminal open set used by V1 lifecycle (at least `active`, `registration_open`, `registration_locked`, `preparing`; legacy `registration` if present).

**Forbidden**: Bulk forfeit fixtures solely because Discord is down.

## Resume

1. Require `pause_started_at`
2. `delta = now - pause_started_at`
3. Rebase unresolved matchday + unplayed fixture windows by `delta`
4. `status = active`, clear `pause_started_at`, accumulate `total_paused_seconds`

## Play while paused

Manager Play / deadline advance that consumes windows: **Block** with clear paused reason (not “ask Discord admin”).
