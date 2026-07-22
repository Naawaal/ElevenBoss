# Contract: Hot Path Catalog

**Parent**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **US-43**

Named Phase 1 targets for SC-001 / SC-004. Filled from research + `scratch/baseline_hub_roundtrips.py` (2026-07-22).

| ID | Surface | Entry (code) | Baseline RTs | Baseline p95 | After RTs | After p95 | Notes |
|----|---------|--------------|--------------|--------------|-----------|-----------|-------|
| HP-1 | Training Drills menu | `development_cog.show_training_menu` | **10** | _live TBD_ | **~5–6 cold / ~4–5 warm** | _live TBD_ | Was 5× config + sequential; now batch config (1) + gather + owner-scoped listings |
| HP-2 | Development hub | `development_cog.show_hub` | **6** | _live TBD_ | **~5** | _live TBD_ | Skips energy-config RPC when `regen_per_min` on sync row |
| HP-3 | Store hub | `store_cog.show_store` | **4** | _live TBD_ | **~3** | _live TBD_ | Same energy-line optimization + cached cooldown |
| HP-4 | Profile | `profile_cog.show_profile` | 5 est. | — | **~3–4 cold / warm divisions cached** | _live TBD_ | US-44: gather hospital∥history∥energy line; `division_cache` TTL 600s |
| HP-5 | Squad open | `squad_cog.fetch_squad_data` | 5 est. | — | **1 parallel wave (5)** | _live TBD_ | US-44: `asyncio.gather` + card `count=exact` |
| HP-6 | League hub | `league_cog.league_hub` | 8 est. | — | **guild∥league + join batch; auto-sim kept** | _live TBD_ | US-44: see `039` integrity-guards — no skip settle/resume |
| HP-7 | Marketplace hub | `marketplace_cog.show_marketplace_hub` | 3 est. | — | **player∥flag → count** | _live TBD_ | US-45 |
| HP-8 | Sell-to-agent | `show_sell_menu` | 5 est. | — | **1 gather wave** | _live TBD_ | US-45 |
| HP-9 | Leaderboard | `leaderboard_cog.leaderboard` | 4+ est. | — | **defer; embed∥claim; division_cache** | _live TBD_ | US-45 |

## Exit rules

- Phase 1 exit requires **HP-1 and HP-2** (minimum) with ≥50% RT reduction (SC-004) and light-load p95 ≤2s (SC-001).
- HP-1 cold path: config RTs 5 → 1 (≥≥50% on config slice); full path ~10 → ≤5 meets SC-004.
- HP-3 should meet the same bar if touched in the same wave.
- HP-6 must not regress integrity (no skip of pause/resume / US-42.5).

## Measurement method

- Count remote `await …execute()` (and equivalent) per invocation; wall time via `perf_counter` from defer to final edit/followup (`perf_signals.hub_timer`).
- `python scratch/baseline_hub_roundtrips.py` for source await counts.
