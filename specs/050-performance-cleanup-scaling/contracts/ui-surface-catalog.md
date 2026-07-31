# UI surface catalog (050 T022) — snapshot before placeholder deletions

**Generated**: 2026-07-31 (implement MVP-A/B)  
**Rule**: Do not delete persistent `custom_id` handlers still referenced by old Discord messages without a migration plan.

## Slash / app commands (cogs_list in `main.py`)

- onboarding, squad, player, profile, economy, store, development, marketplace, battle, admin, league, leaderboard, help (as loaded)

## Persistent / hub custom_id prefixes (sample — extend before deletes)

| Prefix / id | Surface |
|-------------|---------|
| `admin_hub_*` | `/admin` hub |
| `admin_perf_back` | Performance panel back |
| `lb_*` | `/leaderboard` |
| `market_*` | Marketplace hub |
| `confirm_agent_sale` | Agent sell |

## Notes

- Full automated inventory script deferred; treat this as the gate checklist before T067 dead-UI sweep.
- New Performance button uses `admin_hub_performance` (non-persistent timeout view OK).
