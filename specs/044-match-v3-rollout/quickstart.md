# Quickstart: Match Engine V3 Production Rollout

**Feature**: `044-match-v3-rollout`  
**Prerequisites**: Migration `083` applied; `041` V3 code on the running bot; Supabase `game_config` writable.

## 1. Regression baseline (flags still off)

```powershell
pytest tests/test_nss_v3_determinism.py tests/test_nss_v3_projectors.py -q
# optional heavier corpus / win-rate:
# pytest tests/test_nss_v3_golden_corpus.py tests/test_nss_win_rates.py -q
```

Expect: green. Bot matches still pin `nss_v2` while flags are `0`.

## 2. Enrichment unit check

After projector changes:

```powershell
pytest tests/test_nss_v3_projectors.py -q
```

Expect: explainability tips use readable hints; empty stream → no invented tips.

## 3. Enable bot V3 (staging / soak guild)

```sql
UPDATE public.game_config
SET value_json = '1'::jsonb
WHERE key = 'match_engine_v3_bot';
-- leave league + friendly at 0
```

**Config cache:** `get_game_config_int` uses a process-local TTL of **300 seconds** (`apps/discord_bot/core/config_cache.py`). After flipping a flag, either wait ~5 minutes for TTL expiry **or restart the bot** so new kicks read the new value. Invalidation only runs after in-process config writes via the bot — raw SQL updates do not auto-bust the cache.

## 4. Discord smoke — bot

1. `/battle` → Bot Battle → complete a match.  
2. Confirm Decision Windows / transition styles behave as V3.  
3. Post-match shows **How it was decided** when moments exist.  
4. SQL: latest bot `match_runs.engine_version = 'nss_v3'`.  
5. Rewards applied once (coins/XP/fatigue).  

Repeat to build soak count (see [soak-and-rollback.md](./contracts/soak-and-rollback.md)).

## 5. Rollback drill

```sql
UPDATE public.game_config
SET value_json = '0'::jsonb
WHERE key = 'match_engine_v3_bot';
```

New bot kick → `nss_v2`. Any in-flight v3 run still finishes on v3.

## 6. League enable (only after soak)

```sql
UPDATE public.game_config
SET value_json = '1'::jsonb
WHERE key = 'match_engine_v3_league';
```

Smoke: one live league Play + one auto-sim; standings/points once; explainability on live finalize when events exist.

## 7. Changelog

When bot (then league) is live for real managers, add a short player-facing note to `change_log.md`.

## Contracts

- [engine-flag-rollout.md](./contracts/engine-flag-rollout.md)  
- [explainability-ui.md](./contracts/explainability-ui.md)  
- [soak-and-rollback.md](./contracts/soak-and-rollback.md)  
)
