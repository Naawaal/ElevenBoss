# Contract: Development Mentor UI

**Feature**: `006-mentor-transfusion`  
**Surfaces**: `/development` Allocate Skills; `/player-profile` (Ready copy only)

## Allocate Skills branching

When manager opens skills for card `C`:

| Condition | UI |
|-----------|-----|
| `overall < potential` and `skill_points > 0` | **Existing** six stat buttons (unchanged) |
| `overall < potential` and `skill_points == 0` | Existing empty copy |
| `overall >= potential` and `skill_points >= 5` | **Mentor Ready** embed + **Mentor Transfer** button (no useless allocate-only dead end) |
| `overall >= potential` and `0 < skill_points < 5` | Mentor Ready messaging + disabled/grey transfer (“need 5 SP”) |
| `overall >= potential` and `skill_points == 0` | Copy that card is maxed; earn SP via matches to unlock mentoring |

Optional polish: hide or disable the six allocate buttons when `overall >= potential` (RPC would reject anyway).

## Mentor Transfer flow (short-lived views)

```text
Mentor Transfer
  → Target select (same-club, overall < potential, level < 100; sort by level ASC, then name)
  → Amount buttons: [1 MP] [3 MP] [5 MP] [Max]
       Max = mentor_max_units(source_sp, target_xp); disable amounts > max
  → Confirm embed: SP spent, MP, XP, level before→after (simulate_apply_card_xp), daily remaining
  → Confirm → defer → assert_not_in_match → rpc transfer_mentor_xp
  → Cancel → back; no writes
```

**Interaction rules**

- `defer` immediately on every button/select that hits DB.
- Owner-only (interaction user must match hub owner).
- On RPC error: ephemeral/followup with mapped `api_errors` message; balances unchanged.
- On success: show result (levels gained, SP left, transfers remaining); allow Back to Development hub.
- Prefer non-persistent views (message-bound), same family as fusion subviews — only register persistent views in `main.py` if a `custom_id` must survive restart (v1: avoid).

## Player profile

For maxed cards (`overall >= potential`) with any SP:

```text
⭐ Skill Points Available
**{sp}** · 🎓 Mentor Ready
Converts to: {sp//5} MP ({(sp//5)*500} XP)
```

Non-maxed: keep existing `**{sp}**` only.

No new profile Mentor button in v1; existing Allocate Skills entry (if shown) remains.

## Optional env gate

If `MENTOR_TRANSFUSION_ENABLED` is false/0: treat UI as pre-feature (no Mentor Transfer button / Ready chrome). RPC may still exist for ops testing.

## Regression expectations

- Non-maxed allocate path identical
- Fusion / drills / evolutions / claim rewards untouched
- No new slash commands
