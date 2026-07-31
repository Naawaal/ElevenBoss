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
| 2026-07-31 | standings played fixtures | `idx_league_fixtures_season_played` (091) | **1.452 ms** Bitmap season + Filter removed 56/56 | **0.126 ms** Index Scan played partial | **Ship 091** — `20260731T142205Z` → `142345Z` |
| 2026-07-31 | division LB window | `idx_players_division_lb_human` + drop bare `idx_players_division` (091/092) | Index Scan bare division + **Sort** (~0.16 ms) | **Index Only Scan**, no Sort (**0.088 ms**) | **Ship 091+092** — `20260731_after092_div_after_092.txt` |
| 2026-07-31 | global LB window | `idx_players_global_lp_human` (091) | Seq Scan + Sort (tiny N) | Index Only Scan when seqscan disabled (`forced_index_use.txt`); planner still seqscans at ~30 humans | **Ship 091** — growth path; revisit if seqscan persists at larger N |
| 2026-07-31 | Transfer Board browse | none | Index Scan `transfer_listings_status_expires_idx` + tiny Sort (6 rows) | n/a | **Waive T036** — no new index |

## Indexes

Indexes in migration 080+ must reference which EXPLAIN motivated them. No speculative FK indexes.
