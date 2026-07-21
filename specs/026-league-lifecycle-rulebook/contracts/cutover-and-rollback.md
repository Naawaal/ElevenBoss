# Contract: Cutover and Rollback

**Feature**: `026-league-lifecycle-rulebook`  
**Clarification**: Q3 = feature-flagged exclusive per-guild cutover

## End state

```text
020/021 living season
  → grandfather until completion (no mid-season ruleset rewrite)
  → guild cutover flag becomes effective
  → every future season uses Lifecycle Rulebook V1 exclusively
```

## Effective cutover

```text
global = league_lifecycle_v1_enabled()
guild  = guild_config.league_lifecycle_v1_enabled  # NULL | true | false
effective = global AND (guild IS NULL OR guild IS TRUE)
```

Additional guard: do not start a V1 season while a non-V1 season is still open (`registration*` / `active` / `paused` / `settling` under legacy/dynamics ruleset). Wait for completion, then V1-only.

## Version columns

Every V1 season stores:

- `ruleset_version` (e.g. `lifecycle-v1`)
- `engine_version` (deploy identifier)
- `ruleset_snapshot` JSONB

## Dual modes

**Forbidden** as a permanent product: selectable “Dynamics vs Lifecycle” league modes.

During rollout only: grandfather non-V1 seasons + V1 for cutover guilds.

## 021 fate

After successful rollout, `league_state_machine_job` / automation module is a **thin wake-up**:

```text
await league_lifecycle_engine.process_due_transitions(now)
await publish_pending_outbox(...)
await recover_stalled_operations(...)
```

No divergent registration/start/prize logic in the job.

## Rollback

1. Disable global and/or guild cutover flags → **stop creating new V1 seasons**.  
2. Do **not** convert an active V1 season back to Dynamics.  
3. Living V1 seasons finish under V1 ruleset snapshot.
