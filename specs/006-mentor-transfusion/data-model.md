# Data Model: Mentor Transfusion

**Feature**: `006-mentor-transfusion` | **Date**: 2026-07-11

## Persisted entities (new)

### `mentor_transfer_log` (append-only)

One row per **successful** Mentor Transfer. Used for daily cap enforcement and audit.

| Column | Type | Rules |
|--------|------|-------|
| `id` | `BIGSERIAL` / `UUID` | PK |
| `club_id` | `BIGINT` | FK → `players.discord_id`; club that owns both cards |
| `source_card_id` | `UUID` | Source at time of transfer (keep even if card later sold) |
| `target_card_id` | `UUID` | Target at time of transfer |
| `mentor_units` | `INTEGER` | `N ≥ 1` |
| `sp_spent` | `INTEGER` | Exactly `5 * N` |
| `xp_granted` | `INTEGER` | Exactly `500 * N` (amount passed into `apply_card_xp`) |
| `transfer_date` | `DATE` | `CURRENT_DATE` (UTC session / DB timezone — document as UTC date in RPC) |
| `created_at` | `TIMESTAMPTZ` | Default `now()` |

**Indexes**: `(club_id, transfer_date)` for daily `COUNT(*)`.

**RLS**: Enable RLS; policies for `anon, authenticated, service_role` — at minimum `SELECT` + `INSERT` the bot needs (bot uses service/anon key patterns already used for `fusion_daily_log`). Prefer matching fusion grant style + explicit policies so empty-policy trap cannot occur.

**Mutations**: INSERT only from `transfer_mentor_xp`. No UPDATE/DELETE in app code.

**Daily cap**: `COUNT(*) WHERE club_id = $club AND transfer_date = CURRENT_DATE` must be `< 3` before insert; after insert must be `≤ 3`.

## Persisted entities (existing — mutated)

### `player_cards` (source)

| Field | Mutation on success |
|-------|---------------------|
| `skill_points` | `-= sp_spent` |
| `skill_points_spent` | `+= sp_spent` |

Must remain `skill_points >= 0` and consistent with earned/spent invariant.

### `player_cards` (target)

Mutated **only** via `apply_card_xp(target_id, xp_granted, 'mentor_transfer')`:

| Field | Effect |
|-------|--------|
| `xp`, `level` | Normal XP pipe |
| `skill_points`, `skill_points_earned` | On level-ups (+3/level) |
| `player_xp_log` | Existing append from `apply_card_xp` |

No direct `UPDATE` of target XP/level in the mentor RPC outside `apply_card_xp`.

## View / ephemeral entities (not stored)

### Mentor preview (Discord confirm screen)

| Field | Source |
|-------|--------|
| Source name, SP before/after | Card row + math |
| Target name, level before → after | `simulate_apply_card_xp` |
| Mentor units `N`, SP spent, XP granted | `mentor_math` |
| Daily transfers used / remaining | `COUNT` on log for today |

### Eligibility (derived)

| Role | Predicate |
|------|-----------|
| Source | `owner_id = club`, `overall >= potential`, `skill_points >= 5` |
| Target | `owner_id = club`, `id ≠ source`, `overall < potential`, `level < 100`, headroom ≥ 500 for at least 1 unit |

## State transitions

```text
[Idle]
  → manager opens Allocate Skills on maxed source with SP ≥ 5
[MentorReady]
  → pick target → pick N → confirm preview
[Confirm]
  → RPC success → [Transferred] (log row + balances updated)
  → RPC reject / cancel → [Idle] (no writes)
```

Daily counter is not a separate state machine — it is derived from log rows for `transfer_date`.

## Validation rules (summary)

- `N` integer ≥ 1; `sp_spent = 5N`; `xp_granted = 500N`
- Source SP ≥ `sp_spent` before debit
- Target XP headroom to `L_MAX` ≥ `xp_granted` (else reject)
- Club daily successful transfers &lt; 3 before commit
- Same `owner_id` on source and target; both exist
- Injury/fatigue on source: **ignored** (allowed)
- Coins/energy: **never** touched

## Out of scope persistence

- No `game_config` keys for mentor rates in v1 (code constants)
- No `skill_points_mentored` column
- No marketplace / match schema changes
