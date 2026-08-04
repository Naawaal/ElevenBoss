# Quickstart: Ranked PvP Matchmaking and Manager Rivalries

**Feature**: `053-pvp-matchmaking-rivalries`  
**Purpose**: Runnable validation after migration **098** + bot wiring. Not an implementation guide.  
**Gate**: Do not enable production PvP until Feature **052** ACCEPT — see [GATE.md](./GATE.md).

## Prerequisites

- Migrations through **098** on a clone/dev DB
- `verify_required_schema.sql` / `scratch/verify_schema_full.py` green (includes 098 guards)
- `battle_pvp_enabled=false` by default; enable only on internal guild for soak
- pytest for `packages/pvp`
- Two Discord test managers in the **same** guild with valid XIs and energy

## 1. Pure package tests

```bash
pytest tests/test_pvp_matchmaking.py tests/test_pvp_rivalry_math.py tests/test_pvp_reward_policy.py -q
```

**Expect**: widening bands; pair score order; block/cooldown exclusions; rivalry activate at 3/30d; dormant 60d; only `pvp` yields non-zero LP in policy helpers.

## 2. Schema / RPC smoke

1. Apply `098_pvp_matchmaking_rivalries.sql` via `scratch/apply_migration_098.py`.
2. Confirm tables `pvp_matchmaking_queue`, `manager_rivalries`, `pvp_blocks`; `match_runs.run_type` accepts `pvp`/`practice`.
3. `join_pvp_queue` with flag false → rejected.
4. Enable flag on clone; join does **not** reduce energy.

## 3. Matchmaking concurrency

| Setup | Action | Expect |
|-------|--------|--------|
| Two searching same guild | `try_match_pvp_queue` once | One run; both matched |
| Double claim race | two parallel try_match | Still one run |
| Different guilds | try_match | No pair |
| Block either direction | try_match | No pair |
| Same pair within cooldown | try_match | No pair |

## 4. Stadium + finalize (internal)

1. Pair two managers → one shared thread; both mentioned.
2. Complete live playback (or fast-forward harness).
3. `finalize_pvp_match` once → both coins/XP/LP; second call idempotent.
4. Thread create failure before kickoff → abandoned, locks released, energy unchanged.

## 5. Practice isolation

1. AI Practice match → embed shows No Global LP; `global_lp` unchanged; rivalry unchanged.
2. Attempt non-zero LP on practice finalize → SQL reject.
3. Friendly match → still zero rewards/LP/rivalry.

## 6. Rivalries (slice 2)

1. Three ranked meetings within 30 days → status `active`; full-time rivalry field.
2. Rivalries hub shows H2H; Friendly Rematch does not increment meetings.
3. Block prevents queue pair and Friendly invite.

## 7. Rollback

1. Set `battle_pvp_enabled=false` (and optionally `pvp_rewards_enabled` / `pvp_rivalries_enabled`).
2. Find Opponent unavailable; legacy Bot Battle path available.
3. Historical PvP/rivalry rows retained.
4. Matchmaker job remains safe no-op when flag off / empty queue.

### Flag stages (internal soak)

| Stage | Flags | Intent |
|-------|-------|--------|
| Dark | all false | Schema live, hub legacy |
| Queue only | `battle_pvp_enabled=true`, rewards/rivalries false | Pair + stadium without LP economy |
| Rewards | + `pvp_rewards_enabled=true` | Coins/XP/LP finalize |
| Rivalries | + `pvp_rivalries_enabled=true` | H2H / badges / board |
| Rollback | flip `battle_pvp_enabled=false` | Instant hub rollback; keep rows |

Keep rollback path available for at least one full soak window before production guild enable.

## 8. Ops scripts

```bash
python scratch/check_053_pvp_ready.py
python scratch/pvp_soak_report.py
python scratch/apply_migration_098.py  # then 099, 100, 101 as needed
```

Migrations: **098** spine → **099** fairness/hub → **100** finalize → **101** rivalries/blocks/recovery.
## Contracts

- [battle-hub-surfaces.md](./contracts/battle-hub-surfaces.md)
- [pvp-queue-rpcs.md](./contracts/pvp-queue-rpcs.md)
- [pvp-finalize.md](./contracts/pvp-finalize.md)
- [ai-practice-policy.md](./contracts/ai-practice-policy.md)
- [rivalry-presentation.md](./contracts/rivalry-presentation.md)
