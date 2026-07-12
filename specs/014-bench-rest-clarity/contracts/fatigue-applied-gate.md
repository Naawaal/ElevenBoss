# Contract: Fatigue applied gate

**Feature**: `014-bench-rest-clarity`

## Problem

`xp_applied_at` is used as a full “rewards done” early return, but fatigue runs **after** XP is marked. Failures leave competitive matches without fatigue forever.

## Contract

### `match_history.fatigue_applied_at`

- NULL until `apply_post_match_fitness` returns without raising.
- Set via helper analogous to `mark_match_xp_applied` (e.g. `mark_match_fatigue_applied`).

### Bot / league reward helpers

```text
existing = fetch_match_reward_row(...)
# create economy/history if needed
if not xp_applied_at:
    apply_match_xp_if_needed(...)
if not fatigue_applied_at:
    try:
        fitness = apply_post_match_fitness(...)
        mark_match_fatigue_applied(history_id)
        # notify overflow if any
    except:
        log + surface short warning to manager (do not raise away coins)
return coins
```

Early return when **both** timestamps are set may still short-circuit for pure coin re-reads, but **must not** skip a pending fatigue apply.

### Idempotency

- Never call `apply_match_fatigue` twice for the same `match_history` id after `fatigue_applied_at` is set.
- Injury side effects are part of the same fitness call — one gate covers both.

### Call sites

- `apps/discord_bot/core/match_rewards.py`
- `apps/discord_bot/core/league_rewards.py`
- `apps/discord_bot/core/match_runs.py` (fetch columns + mark helper)
