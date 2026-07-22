# Implementation Plan: Hub Hot-Path Wave 2

**Branch**: `039-hub-hot-path-wave2` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**US citation**: US-44 (extends US-43); league integrity US-42.5

## Summary

Apply US-43 patterns to HP-4…HP-6: `asyncio.gather`, config batch/cache for league join gates, TTL-cache `global_divisions`, card **count** instead of id dump on squad, `hub_timer` on all three opens. No Redis, no new commands, no skipping league auto-sim/pause-resume.

## Technical Context

**Language**: Python 3.11+  
**Deps**: Existing discord.py + supabase client; reuse `config_cache`, `economy_rpc`, `perf_signals`  
**Storage**: No new migrations in MVP (081 already provides batch config)  
**Testing**: pytest source/contract tests + optional scratch await counts  
**Constraints**: Monorepo; Principle II; YAGNI

## Constitution Check

| Gate | Status |
|------|--------|
| I Monorepo | PASS — changes in `apps/discord_bot` only |
| II RPC/client | PASS — PostgREST + existing RPCs |
| IV Defer | PASS — unchanged |
| VII YAGNI | PASS — no dashboard RPC until measured need |

## Project Structure

```text
specs/039-hub-hot-path-wave2/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── hot-path-wave2.md
    └── integrity-guards.md

apps/discord_bot/cogs/league_cog.py      # gather + join limits
apps/discord_bot/cogs/squad_cog.py       # gather + count
apps/discord_bot/cogs/profile_cog.py     # gather + divisions cache
apps/discord_bot/core/division_cache.py  # optional thin helper (or inline)
tests/test_hub_hot_path_wave2.py
```

## Implementation phases

1. **Spec lock** — this package  
2. **League** — `_league_join_limits` batch; parallel guild_config+leagues; smarter reg count; hub_timer  
3. **Squad** — gather + count; hub_timer on `/squad`  
4. **Profile** — gather hospital∥history where safe; divisions cache; hub_timer  
5. **Verify** — pytest, catalog After RTs, change_log, feature.json

## Complexity Tracking

None — reuses US-43 primitives.
