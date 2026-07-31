# Quickstart: Performance, Cleanup & Scalability Hardening

**Feature**: `050-performance-cleanup-scaling`  
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Validation guide for implementers — not a full task list (`/speckit.tasks` owns that).

---

## Prerequisites

- Repo checkout with `.env` pointing at **dev/staging** for load/EXPLAIN (never load-test production Discord)
- Python 3.11+; `pip install -r requirements.txt` (after Phase 1: includes `-e packages/energy`)
- Ops DB tools: `requirements-ops.txt` when applying migrations via scratch scripts
- Read contracts: [round-trip-budgets](./contracts/round-trip-budgets.md), [cursor-pagination](./contracts/cursor-pagination.md), [cache-policy](./contracts/cache-policy.md), [observability](./contracts/observability.md), [job-idempotency](./contracts/job-idempotency.md)

---

## Phase 1 — Cleanup & measurement gates

```bash
# Dead packages must have zero live imports
rg -n "\btraining\b|from training|import training" apps packages tests scripts scratch
rg -n "training_engine" .

# Energy install
python -c "import energy; print(energy.__file__)"

# Alembic/ORM gone from runtime import surface (after dep cut)
rg -n "alembic|sqlalchemy|from sqlalchemy" apps packages

# Sentry initializes only with DSN (smoke)
# Start bot with SENTRY_DSN set; confirm startup log / no crash without DSN

# Perf snapshot
# Owner: /admin → Performance (after panel ships)
```

**Pass**: packages deleted; energy importable; no alembic in apps; Sentry optional-init OK; perf signals emit hub samples.

---

## Phase 2 — Hot-path RPC gates

1. Apply additive migration `090_*` via `scratch/apply_migration_090.py` (pattern from prior scratch scripts).
2. Run `supabase/scripts/verify_required_schema.sql` (or `python scratch/verify_schema_full.py`).
3. Structural tests:

```bash
python -m pytest tests/test_leaderboard_page_budget.py tests/test_market_browse_server_filter.py tests/test_hub_round_trip_budgets.py -q
```

4. Manual Discord (staging bot):

| Check | Expect |
|-------|--------|
| `/leaderboard` Division, multi-page | Page ≤10 rows; rank/cutoffs sensible; no multi-second stall on large division |
| Global tab | Stable order on LP ties; viewer rank coherent |
| Marketplace Transfer Board + filters | Matches outside old “first 50” appear; page ≤25 |
| Sell menu | Same eligibility as before; faster/single load |
| `/development` | Same display; **no** surprise legendary create on open |

5. Compare `perf_signals` before/after for `leaderboard`, `marketplace`, `development` (SC-002 ≥50% RT cut on targeted hubs).

**Pass**: budgets met; UI parity; additive migration verified; old bot build still runnable against new RPCs.

---

## Phase 3 — Cache gates

```bash
python -m pytest tests/test_config_cache.py tests/test_cache_backend.py -q  # as added
```

- Hit rate Tier 1–2 ≥80% in steady soak logs  
- Mutation (spend coins / energy) still fails closed on insufficient balance (cache not authoritative)

---

## Phase 4 — Index gates

- Capture `EXPLAIN (ANALYZE, BUFFERS)` before/after for division page + market browse  
- Only ship indexes with evidence attached to PR / `contracts` note  
- Re-run verify schema guards

---

## Phase 5 — Flag maturity (separate release)

1. Inventory Mentor / V3 / league flags (from research).  
2. Soak V3 all modes = 1; monitor failures/settlement.  
3. Only then default V3, stop new V2, drain, delete V2 execution.  
4. **Do not** combine with Phase 2 RPC deploy.

---

## Load tests (staging data plane)

```bash
python scripts/load/leaderboard_read.py --concurrency 50
python scripts/load/marketplace_browse.py --concurrency 50
python scripts/load/mixed_workload.py --concurrency 100
```

Stop escalating at saturation knee; record p95, 429 rate, errors.

---

## Rollback

1. Redeploy previous bot image/commit.  
2. Leave additive RPCs/indexes in place (harmless).  
3. Do not drop Phase 2 functions until old path fully removed and soak complete.

---

## Out of scope here

- Production rarity-potential DM finish (`049`)  
- Raising HTTP pool before Phase 2 RT wins  
- Redis enablement (Phase 7)
