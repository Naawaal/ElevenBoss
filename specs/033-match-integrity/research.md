# Research: Match Integrity (US-42.4)

**Date**: 2026-07-22 | **Feature**: `033-match-integrity`

## R1 — Settlement vs presentation order

**Decision**: On bot/league happy paths, mark durable run completion (and fixture played where applicable) **before** Discord `finalize_match` / result embeds. If presentation throws, **retry present only** — do not call `abandon_run` after rewards succeeded.

**Rationale**: Spec FR-002/004; today’s bot path can `abandon_run` after pay when embed fails (Critical).

**Alternatives considered**: Single mega-RPC that also posts Discord — impossible (Discord outside DB). Ignore status drift — rejected (support/ops lies).

## R2 — Idempotency keys (keep)

**Decision**: Keep `apply_club_economy` keys `match:{run_id}:{club_id}` and `process_match_result` / `xp_applied_at` short-circuit. Do not invent a second ledger key scheme.

**Rationale**: Already correct for double-settle economy/XP; gaps are status/lock/present, not missing ledger uniqueness.

## R3 — INV-10 / friendly

**Decision**: No code change required for evo tick site — only inside `process_match_result`; Python has zero direct tick callers; friendly remains logs-only. Add regression tests/grep guards.

**Rationale**: Historical bug closed; US-42.4 locks it with tests.

## R4 — Abandon + lock atomicity

**Decision**: Migration **077** adds `abandon_match_run(p_run_id)` (set abandoned/failed + `release_match_lock` for home/away/active humans) and `reconcile_orphaned_match_locks()` (delete locks with no streaming/completing run for that club). Replace blind startup `match_locks` wipe with reconcile (+ abandon incomplete ephemerals).

**Rationale**: FR-006/014; blind wipe unlocks clubs while league runs may still be `streaming`.

## R5 — Bot restart recovery

**Decision**: If interrupted bot run already has rewarded `match_history` / economy for `run_id`, **`complete_run`** instead of abandon. Else abandon via new RPC (clears lock).

**Rationale**: Spec US4 — settle once from durable state when pay already happened.

## R6 — League play locks

**Decision**: `execute_league_match` acquires MatchLocked for **both** human clubs (parity with `league_lifecycle_engine`), releases both in `finally`. On hard fail after lock, abandon/reconcile run so fixture isn’t stuck streaming unlocked.

**Rationale**: Critical gap — opponent could mutate mid human-triggered league sim.

## R7 — Career stats double-count

**Decision**: Soft — document; prefer fixing only if cheap (idempotent career increment keyed by run) in same wave; else defer to follow-up with ponytail note.

**Rationale**: Coins already protected; career counters Soft per audit.

## R8 — Migration number

**Decision**: **`077_match_integrity_guards.sql`**.

## R9 — Pure module

**Decision**: Optional tiny `classify_interrupted_run(...)` in `packages/` for recovery unit tests; skip if recovery logic stays ≤ one function in `match_recovery.py`.

**Rationale**: YAGNI — don’t add package file unless tests need pure branch table.
