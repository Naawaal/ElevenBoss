# Contract: Cache Policy & Key Catalog

**Parent**: [../spec.md](../spec.md) | **Clarifications**: Q2 (economy tunables)

## Layers

| Layer | When |
|-------|------|
| `process` | Phase 0–2 default (single bot instance) |
| `shared` | Phase 3+ multi-instance for mutable summaries + **economy-priced** tunables |
| `active_invalidate` | Alternative to shared for economy tunables (broadcast / pub-sub) |

## Key patterns (catalog)

| Pattern | Example | Layer P1 | Layer multi-instance | TTL | Invalidate |
|---------|---------|----------|----------------------|-----|------------|
| `cfg:{key}` | `cfg:drill_basic_energy` | process | **shared or active_invalidate** if priced; else process OK | 300s | config write / admin |
| `cfg:global_divisions:rows` | ladder rows for `/profile` | process | process OK (non-priced) | 600s | admin ladder edit / `invalidate_global_divisions` |
| `cfg_batch:{hash}` | optional memo of many-key fetch | process | same as members | 300s | any member invalidate |
| `profile:{club_id}` | own summary | process | shared only | 30s | XP/SP/match/spend |
| `economy:{club_id}` | coins/energy summary | process | shared only | 10s | economy mutation |
| `standings:{season_id}` | league table | process | shared preferred | 60s | matchday settle |
| `lb:{board}:{period}` | leaderboard | process | shared OK | 300s | recompute job |
| `vote:{discord_id}` | vote claim flag | process | shared if multi | 12h | claim |

## Priced economy keys (must not TTL-only-local under multi-instance)

| Key | Priced? | Notes |
|-----|---------|-------|
| `drill_basic_energy` | yes | Training cost |
| `drill_advanced_energy` | yes | Training cost |
| `drill_basic_xp` / `drill_advanced_xp` | yes | Reward math |
| `drill_advanced_min_level` | no | Gate only |
| `energy_refill_costs` | yes | Store refill |
| `energy_refill_amount` | yes | Store refill |
| `energy_regen_per_min` / `energy_max` | yes | Economy pacing |
| `daily_pack_cooldown_hours` | yes | Pack faucet timing |
| `pack_standard_rarities` / `pack_standard_rarity_weights` | yes | Drop rates |
| `fusion_coins` | yes | Sink |
| `wage_scale_factor` / `wages_payroll_bill_scale` | yes | Payroll |
| `topgg_vote_bypass_enabled` | no | Ops flag |

## Rules

1. Do not invent key strings ad hoc in cogs — add to this catalog in the same PR.
2. Under multi-instance, serving stale **priced** `cfg:*` from process TTL alone is a **defect** (split-brain pricing).
3. Live inventory / active match: **do not cache** (TTL 0).

## Implementation note

Phase 1: `config_cache.get/set/invalidate` only for `cfg:*`. Profile/economy caches optional if SC-004 already met via config alone.

**Write-path invalidation**: call `economy_rpc.invalidate_game_config(key)` (or `invalidate_priced_game_config()`) after mutating `game_config`. That clears this process only. Multi-instance still needs shared cache or broadcast (FR-012) — do not treat process invalidate alone as Phase 3 exit.
