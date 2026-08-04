# Contract: AI Practice policy

**Feature**: `053-pvp-matchmaking-rivalries`  
**RPC**: `finalize_ai_practice_match`

## Rules

| Field | Value |
|-------|--------|
| `run_type` / `match_type` | `practice` |
| Global LP delta | **0** (SQL REJECT if non-zero attempted) |
| Rivalry update | **forbidden** |
| Competitive PvP W-D-L | **unchanged** |
| Global division | **unchanged** |
| Energy | `ai_practice_energy_cost` (default 10) |
| Coins / XP | Reduced vs legacy bot; new vs established multipliers; established daily rewarded cap |
| Injuries / fatigue | Allowed (Practice is a real workout) unless product later softens — **default: apply fitness like bot** for authenticity; document if soak prefers off |

## Hub copy

Result embed MUST state **No Global LP**.

## Rollback

Legacy `run_type='bot'` + `apply_bot_match_rewards` (with LP) remains callable only when `battle_pvp_enabled=false` for soak rollback — not used as the labeled Practice path when flag is on.

## Tests required

- Practice finalize cannot change `players.global_lp`
- Practice finalize cannot mutate `manager_rivalries`
- Client cannot pass `match_type='pvp'` into Practice finalize
