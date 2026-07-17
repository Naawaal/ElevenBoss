# Contract: Training Drills — Recovery Removal

**Feature**: `023-dev-hub-recovery`  
**Surface**: `/development` → Training Drills (`show_training_menu` / `StatDrillView`)

## Must remove

| Item | Notes |
|------|-------|
| `RECOVERY_DRILL_ID` / `"__recovery__"` | Delete constant and all branches |
| Recovery Session `SelectOption` | No longer in drill select |
| `run_drill_callback` recovery branch | No `process_recovery_session` call from drills |
| `_recovery_eligible` on `StatDrillView` | Move/reuse only in Recover UI / packages |
| Training embed lines advertising Recovery | Skill drills only |
| Placeholder text like “Skill drill or Recovery Session...” | Skill-only placeholder |
| Button label “Recover Fitness ⚡” | Drills button stays “Run Drill ⚡” |
| Unused recovery_amount / recovery_energy params on `StatDrillView` | Drop if only used for Recovery |

## Must keep

- Skill drill select + `process_stat_drill`
- Daily drill count display
- Training Ground bonus XP copy
- Injury block for **skill drills** (Hospital guidance) — wording may say drills, not Recover
- Back to Hub

## Copy target (illustrative)

Training embed describes **Skill Drills** (XP, coins, energy, daily slots) and Training Ground passive fatigue as facility flavor only — **not** as an active Recover CTA. Active Recover CTA lives on the main hub.

## Grep zero after ship

```text
RECOVERY_DRILL_ID
__recovery__
Recovery Session
process_recovery_session
```

…inside `StatDrillView` / `show_training_menu` (batch RPC may still exist elsewhere). Player-facing “Recovery Session” naming may remain on the **Recover** hub path if desired, or rename to “Recover” for consistency — pick one term in UI and use it consistently.

## Rollback

Restore the removed Recovery option and training copy from git; remove hub Recover button. See plan Rollback note.
