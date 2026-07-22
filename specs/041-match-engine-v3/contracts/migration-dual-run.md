# Contract: Migration & Dual-Run

**Feature**: `041-match-engine-v3`  
**Deliverable**: 7

---

## Goals

- Zero in-flight cross-engine completions.
- Rollback without data loss.
- No double settlement.

---

## Version pin

On `create_ephemeral_run` / `create_league_run`:

```text
engine_version = "nss_v3" if flag_enabled(run_type) else "nss_v2"
```

Immutable for the run lifetime. Recovery branches:

```text
if run.engine_version == "nss_v2": legacy stream_match / collect_match_events
else: v3 run_to_completion / step adapter
```

---

## Feature flags

Prefer `game_config` keys (ops-tunable):

| key | default | meaning |
|-----|---------|---------|
| `match_engine_v3_bot` | false | new bot runs use v3 |
| `match_engine_v3_league` | false | league live + auto-sim |
| `match_engine_v3_friendly` | false | friendly live |

Env override optional for staging.

---

## Cutover order

1. Enable **bot** in staging → soak → prod bot  
2. Enable **league** auto-sim (silent) → then live Play  
3. Enable **friendly** last (optional; lowest need for `match_events`)

Each stage requires: determinism CI green, win-rate band check, integrity tests, manual smoke.

---

## Dual-running behaviour

| Scenario | Behaviour |
|----------|-----------|
| New match, flag on | v3 pin + events (if bot/league) |
| New match, flag off | v2 pin; no event rows required |
| Restart mid v2 run | v2 recovery path |
| Restart mid v3 run | v3 recovery + event flush resume |
| Flag flips mid-day | **does not** change existing pins |

---

## Rollback

1. Set flags false.  
2. Leave `match_events` in place.  
3. Do not delete v3 historical runs.  
4. If severe feel bug: keep flag off until Phase 0 patch; hotfix on v3 module without forcing v2 rewrites.

---

## Settlement

Unchanged pipes. Both engines must produce compatible `key_events` / score fields for `apply_bot_match_rewards` / league rewards. Contract test: fixture of events → same XP payload builder inputs.

---

## SDD / changelog

On prod enable: update `change_log.md` player-facing note (engine transparency). Reconcile `.specify/specs/v1.0.0` NSS section when behaviour diverges (Wave 2 tactics).
