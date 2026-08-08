# Contract: Match Phase Lifecycle

**Feature**: `057-competitive-bot-match`  
**Engine surface**: NSS `stream_match` / `stream_match_v3` + `MatchState`

## Flag resolution

```text
enabled = env COMPETITIVE_MATCH_ENABLED if set
       else game_config.competitive_match_enabled
       else false
```

When disabled: stream ends at regulation FULL_TIME exactly as today.

## Phase API (conceptual)

```text
MatchPhase = REGULATION | EXTRA_TIME_FIRST | EXTRA_TIME_SECOND | PENALTY_SHOOTOUT | COMPLETE
```

After each regulation stream completion (flag on):

| Condition | Next |
|-----------|------|
| home_score ≠ away_score | COMPLETE, `decided_by=regulation` |
| tied | EXTRA_TIME_FIRST, persist snapshot, emit ET banner event |

ET periods: continue stream for 5 in-game minutes each with fatigue/injury multipliers from config. Persist at period boundaries.

After EXTRA_TIME_SECOND:

| Condition | Next |
|-----------|------|
| score ≠ | COMPLETE, `decided_by=extra_time` |
| tied | PENALTY_SHOOTOUT (hand off to shootout contract) |

## Persistence checkpoints

Must write `competitive_state` (+ scores) at least:

1. Enter EXTRA_TIME_FIRST  
2. Enter EXTRA_TIME_SECOND  
3. Enter PENALTY_SHOOTOUT  
4. After each penalty kick  
5. COMPLETE  

## Recovery

```text
load match_runs where status active/interrupted and competitive_state.phase not COMPLETE
→ reconstruct MatchState + phase
→ if PENALTY_SHOOTOUT: resume shootout from next sequence
→ else: resume ET stream from phase_minute with et seed
→ never resimulate earlier phases
```

Unrestorable → abandon (existing) without inventing scores.
