# Contract: Development Recovery Session UI

**Feature**: `009-fatigue-recovery`  
**Surface**: `/development` → **Training Drills** only (no new slash command)

## Entry

1. Manager opens `/development` → **Training Drills** (`show_training_menu` / `StatDrillView`).
2. Hub description MUST mention Recovery as an option (fatigue restore, 0 XP, energy cost, shares daily drill slots).

## Flow

```text
Select player
  → Choose action: Skill Drill (existing) | Recovery Session (new)
  → If Recovery: confirm embed (fatigue, energy, 0 coins, 0 XP)
  → defer → rpc process_recovery_session → success/error ephemeral
```

## Eligibility (UI hints; RPC is source of truth)

Show Recovery as available when card:
- Not retired, not in active evo
- `injury_tier` empty / not in hospital
- `fatigue < 100`

Disable or reject with copy when ineligible (do not hide the concept entirely on fatigued rosters — managers should see why).

## Copy requirements

| Moment | Must communicate |
|--------|------------------|
| Menu | Trade-off: skill XP vs fatigue recovery |
| Confirm | +N fatigue (config/default 40), 0 XP, energy cost, 0 coins, uses 1 daily drill slot |
| Success | New fatigue value (and optional bar); no level-up fanfare |
| Errors | Map via `api_errors`: fully rested, injured→Hospital, energy, daily limits |

## New `api_errors` keys

| RPC message | Friendly copy (intent) |
|-------------|------------------------|
| `Player is already fully rested` | Player is already at full fitness. |
| `Player is injured — use Hospital` | Injured — treat them in Hospital / profile, not Recovery. |

Reuse existing drill limit / energy strings where messages match.

## Must not

- Add Store physio button
- Register a new persistent hub button beyond Training Drills extension
- Show fake “4 hour remaining” timers
