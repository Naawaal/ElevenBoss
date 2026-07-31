# Contract: Round-Trip Budgets

**Parent**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)  
**Related**: `038` [hot-path-catalog.md](../../038-db-scalability-performance/contracts/hot-path-catalog.md)

## Definition

One **round trip** = one remote `await …execute()` / RPC / equivalent hosted data-API call on the interaction path after defer.

## Targets (after Phase 2)

| Surface | Entry (today) | Budget | Phase 0 baseline (fill) | After |
|---------|---------------|-------:|-------------------------|-------|
| Profile | `profile_cog` | 1–2 | _TBD_ | _TBD_ |
| Squad | `squad_cog.fetch_squad_data` | 1–2 | _TBD_ | _TBD_ |
| Development hub | `development_cog.show_hub` | 1–2 | ~5 sequential | **≤2** (sync + hub-state 093) |
| Drill menu | `show_training_menu` | ≤3 | ~4–6 warm | keep/improve |
| Marketplace hub | `show_marketplace_hub` | 1 | player∥flag → count (~3) | **1 RPC** (090) |
| Transfer Board page | `_board_listings` | 1 | fetch-50 + Python filter | **1 browse RPC** (090) |
| Sell menu | `show_sell_menu` | 1 | 5-gather | **1 RPC** (090) |
| Division leaderboard | `_division_embed` | 1–2 | **unbounded select** | **1 page RPC** (090) |
| Global leaderboard | global embed | 1–2 | limit 100 + maybe count | **1 page RPC** (090) |

## Latency SLOs

| Path | p50 | p95 |
|------|----:|----:|
| Light hub | <300 ms | <750 ms |
| Normal management hub | <500 ms | <1.2 s |
| Heavy leaderboard/market | <800 ms | <1.8 s |
| Mutation after defer | <1 s | <2 s |

## CI / structural gates

- Leaderboard page `len(rows) <= page_size`
- Market browse results all match filters; no Python filter required for correctness
- Hot hub helper annotated max RT; test or scratch counter fails if exceeded
- Config clusters use `get_game_config_many` (pack rarity included)

## Measurement

- `perf_signals.hub_timer` + `inc_round_trip`
- `scratch/baseline_hub_roundtrips.py` (extend for leaderboard/market)
- Do not claim Phase 2 done without before/after on Division LB + Transfer Board + ≥1 hub-state RPC
