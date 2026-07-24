# Contract: Engine Flag Rollout

**Feature**: `044-match-v3-rollout`  
**Extends**: `041` [migration-dual-run.md](../../041-match-engine-v3/contracts/migration-dual-run.md)

## Flag resolution

`resolve_engine_version(db, run_type)`:

| `run_type` | Config key |
|------------|------------|
| `bot` | `match_engine_v3_bot` |
| `league` | `match_engine_v3_league` |
| `friendly` | `match_engine_v3_friendly` |

- Value `1` → (`nss_v3`, simulation_schema_version for Wave)  
- Else → (`nss_v2`, schema 1)

Called from `create_ephemeral_run` / `create_league_run` only for **new** kicks.

## Cutover order (normative)

1. **Bot** enable (staging → soak → prod bot)  
2. **League** enable only after soak criteria pass (auto-sim + live share the same flag)  
3. **Friendly** optional / last  

## Invariants

- Never change `match_runs.engine_version` after insert.  
- Recovery uses stored pin.  
- Settlement pipes unchanged (US-42.4).  
- Friendly sandbox economy unchanged regardless of engine.

## Rollback

Set type key back to `0`. New kicks for that type use v2. In-flight v3 runs finish on v3.
