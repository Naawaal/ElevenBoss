# Contract: Query Plan Gate (FR-020)

**Parent**: [../spec.md](../spec.md)

## Rule

Before merging a consolidated hot-path read (dashboard RPC or nested PostgREST select):

1. Capture **before** plan for the dominant query(ies) (seq scans, join type, estimated/actual rows).
2. Capture **after** plan for the replacement.
3. Accept only if after is **not worse** on the measured metric (execution time and/or buffers) under representative data, **or** document an explicit waiver with rollback path.

## Artifacts

- Store snapshots under `scratch/explain_snapshots/` or paste summaries into the PR / this file’s log table.
- Script: `scratch/explain_hot_paths.py` (Phase 0–1).

## Log table

| Date | Hot path | Change | Before ms | After ms | Decision |
|------|----------|--------|-----------|----------|----------|
| 2026-07-22 | league_fixtures / economy_ledger | Add idx season+matchday, unplayed partial, ledger club+created | pattern-based | **0.081 ms** fixtures season+matchday after 080 (Bitmap Index Scan on `idx_league_fixtures_season_matchday`) | **Ship 080** — confirmed via `scratch/explain_snapshots/20260722T133827Z_*.txt` |

## Indexes

Indexes in migration 080+ must reference which EXPLAIN motivated them. No speculative FK indexes.
