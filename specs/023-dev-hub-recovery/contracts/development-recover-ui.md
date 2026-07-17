# Contract: Development Recover UI

**Feature**: `023-dev-hub-recovery`  
**Surface**: `/development` hub only (no new slash command)

## Hub entry

On `DevelopmentHubView`, add a button (suggested label **💚 Recover**, success/primary style) on an existing hub row that does not force a new slash command or a second Development command.

Hub embed copy may briefly note Recover restores fitness for energy (0 XP) — optional one-liner; do not re-document the full drill economy there.

## Flow (short-lived views)

```text
/development hub
  → Recover
      → Filter eligible roster (≤25 shown; sort overall DESC or fatigue ASC — pick one and keep stable)
      → Empty state if none eligible (Hospital / full fitness / academy guidance)
      → Multi-select (min 1, max 3); each option shows fatigue %
      → Continue (disabled until ≥1 selected)
          → Confirm embed:
                • Player names + current → projected fatigue (or +grant / cap note)
                • Fatigue grant per player (config)
                • Total energy = N × per-player cost
                • 0 XP · 0 coins
          → Confirm → defer → assert_not_in_match → rpc process_recovery_batch
          → Cancel → back to select or hub; no writes
      → Success followup (who recovered, gains, energy spent) + show_hub
```

## Interaction rules

- `defer` immediately on every button/select that hits DB (confirm, hub refresh).
- Owner-only (`interaction.user.id == hub owner_id`).
- Disable controls on submit to reduce double-tap; re-enable on mapped failure.
- On RPC error: ephemeral/followup via `api_errors`; balances unchanged.
- Prefer non-persistent views (message-bound), same family as Mentor / Fusion subviews.
- Timeout: same ~900s hub family; `disable_view_on_timeout`.

## Eligibility shown in select

Include card only if all are true:

- owned by manager
- not `is_retired`, not `in_academy`
- `injury_tier` is null and not `in_hospital`
- `fatigue < 100`
- not in active evolution (if cheap to query)
- not on transfer list (if cheap to query)

## Copy expectations

- Success: names + fatigue deltas + energy spent; remind 0 XP.
- Hospital block messaging points to `/profile` → Manage Hospital, **not** Training Drills.
- Insufficient energy: same class of affordability messaging as other Development spends.

## Regression expectations

- Training Drills path has **zero** Recovery controls (see [drills-recovery-removal.md](./drills-recovery-removal.md))
- Allocate Skills / Mentor / Fusion / Evolutions / Claim unchanged except sharing hub row space
- No new slash commands
- No persistent `custom_id` registration required in `main.py` for v1
