# Quickstart: Validate US-43

**Feature**: `038-db-scalability-performance`  
**Specs**: [spec.md](./spec.md) · [plan.md](./plan.md) · [contracts/](./contracts/)

Validation guide for operators/devs after implementation. Not a full test suite.

---

## Prerequisites

- Repo checkout on branch `038-db-scalability-performance` (or main with US-43 merged)
- `.env` with `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL` (for EXPLAIN / apply scripts)
- Python venv with project deps installed (`psycopg` for scratch apply scripts)
- Bot can reach Discord test guild (manual hub checks)

---

## 1. Schema / indexes

```bash
python scratch/apply_migration_080.py
python scratch/apply_migration_081.py
python scratch/apply_migration_082.py
# Guard
python scratch/verify_schema_full.py
# or: psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

**Expect**: Migrations apply cleanly; verify script exits 0; `get_game_config_many`, `claim_daily_pack(..., text)`, `pack_claim_runs` guarded.

---

## 2. Baseline → after round-trips

```bash
python scratch/baseline_hub_roundtrips.py
```

**Expect**: Numbers recorded into [contracts/hot-path-catalog.md](./contracts/hot-path-catalog.md). After Phase 1 code: ≥50% RT drop on HP-1 config slice / overall path (SC-004).

---

## 3. Query plan gate

```bash
python scratch/explain_hot_paths.py
```

**Expect**: Snapshots under `scratch/explain_snapshots/`; fixtures query uses `idx_league_fixtures_season_matchday` ([query-plan-gate.md](./contracts/query-plan-gate.md)).

---

## 4. Unit checks

```bash
pytest tests/test_config_cache.py tests/test_idempotent_outcome.py tests/test_db_retry.py tests/test_pack_claim_idempotency.py tests/test_job_claims.py -q
```

**Expect**: TTL expiry, invalidate, `replay`→`already_applied`, retry bounds, pack SQL contract, job key helpers.

---

## 5. Manual Discord checks (persona)

| Persona | Action | Expect |
|---------|--------|--------|
| Manager | `/development` → Training Drills | Fast hub; costs/energy correct vs pre-change |
| Manager | `/store` | Hub loads; login/refill still atomic |
| Manager | Double-tap pack / retry after timeout | Success or `already_applied` copy — **no** false failure / duplicate cards |
| Manager | Open hubs twice within TTL | Second faster; config values unchanged |
| Ops | Grep logs for `perf.hub` / `perf.cache` | Signals present ([observability-signals.md](./contracts/observability-signals.md)) |

---

## 6. Observability smoke

- Trigger HP-1 twice; confirm logs show `perf.hub` / `perf.cache` hit on second call.
- Unit: `tests/test_db_retry.py` covers transient retry.

---

## Phase 3 preview (SC-006)

See [job-claim-catalog.md](./contracts/job-claim-catalog.md):

1. Two bot processes, same DB.
2. Trigger `daily_recovery_job` on both.
3. One runs `process_daily_recovery`; other logs skip.
4. Do **not** enable multi-instance prod until drill passes.
5. Economy-priced config: process `invalidate_game_config` is shipped; shared/active invalidation still required for FR-012 under multi-instance.
6. Unit stand-in: `pytest tests/test_job_claims.py::test_sc006_second_claim_skips_work`.

---

## Done when

- [x] Hot-path catalog baselines + after filled for HP-1/HP-2
- [x] SC-004 evidenced on catalog (config RT cut); SC-001 live p95 ops-validated in Discord
- [x] Query-plan log has accepted row for fixtures index
- [x] Pytest green for US-43 modules (`test_config_cache`, `test_job_claims`, …)
- [x] Catalog scheduler jobs wrapped via `run_claimed_job`
- [x] No new slash commands; US-42 pipes unchanged