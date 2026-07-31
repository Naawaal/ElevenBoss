# Contract: Cache Policy

**Parent**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

## Abstraction

```text
CacheBackend
  get(key) -> value | None
  set(key, value, ttl_seconds)
  delete(key)
  delete_prefix(prefix)
  get_or_set(key, ttl, factory)   # single-flight in memory backend
  stats() -> hits, misses, entries, hit_rate
```

Location (plan): `apps/discord_bot/core/cache/{backend,memory}.py`.  
`config_cache.py` becomes a thin adapter or moves behind this API.

## Tiers

| Tier | Example key | TTL | Invalidate when |
|------|-------------|-----|-----------------|
| 1 Config | `cfg:{key}` | ≥5 min | Admin/config mutation |
| 2 Guild | `guild:{id}:config` | 5–15 min | `/admin` guild changes |
| 3 Profile display | `player:{id}:profile` | 15–30 s | Economy, facility, match settle, promo, daily login |
| 4 Standings / LB first | `season:{id}:standings`, `division:{d}:lb:first` | 15–60 s | Results, league reset |

## Forbidden

Never use cache as authority for: coins, energy, card/listing ownership, match locks, SP, evolution claim status, league registration uniqueness.

## Stampede

Memory backend: per-key single-flight (`get_or_set`).  
Multi-instance later: short L1 TTL + optional Redis L2 / pub-sub invalidation (Phase 7).

## Success signal

Steady-state Tier 1–2 hit rate ≥80% after Phase 3 (SC-006).
