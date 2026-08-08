# Data Model: Competitive Bot Match (057)

**Feature**: `057-competitive-bot-match`  
**Date**: 2026-08-08

## 1. Match phases (engine + persisted)

```text
REGULATION → EXTRA_TIME_FIRST → EXTRA_TIME_SECOND → PENALTY_SHOOTOUT → COMPLETE
```

Short-circuit: regulation decisive → COMPLETE; ET decisive after second period → COMPLETE (skip pens).

### Persisted competitive snapshot (on `match_runs`)

Prefer JSONB `competitive_state` (new column) **or** nested under `squad_snapshot.competitive` if column churn is undesirable. Plan default: **`competitive_state JSONB`** for clear query/recovery.

| Field | Type | Notes |
|-------|------|--------|
| `match_phase` | text | enum above |
| `phase_minute` | int | in-phase clock |
| `regulation_home_score` / `away` | int | locked at 90' |
| `extra_time_home_score` / `away` | int | ET goals only (or absolute with regulation base — pick one scheme and stick to it; prefer absolute football score + phase markers) |
| `home_score` / `away_score` | int | live football score (synced with run columns) |
| `et1_seed` / `et2_seed` / `shootout_seed` | text/int | derived from `sim_seed` |
| `penalty_state` | object | see below |
| `decided_by` | text \| null | set at COMPLETE |

Football score never includes shootout conversions.

## 2. `PenaltyShootoutState` (pure + JSON)

| Field | Type |
|-------|------|
| `home_kicks_taken` / `away_kicks_taken` | int |
| `home_penalties_scored` / `away_penalties_scored` | int |
| `home_taker_order` / `away_taker_order` | uuid[] |
| `home_taker_index` / `away_taker_index` | int |
| `sudden_death` | bool |
| `completed` | bool |
| `winner_club_id` | bigint \| null |
| `events` | PenaltyKickEvent[] |

### `PenaltyKickEvent`

| Field | Type |
|-------|------|
| `sequence` | int |
| `club_id` | bigint |
| `player_id` | uuid |
| `goalkeeper_id` | uuid |
| `outcome` | `goal` \| `saved` \| `missed` |
| `seed_key` | text | `shootout_seed + sequence` for audit |

## 3. `player_suspensions`

```text
id UUID PK
player_card_id UUID NOT NULL  → player_cards
club_id BIGINT NOT NULL       → players / owner
reason TEXT NOT NULL          CHECK IN ('second_yellow','straight_red')
source_match_run_id UUID NOT NULL → match_runs
matches_total SMALLINT NOT NULL
matches_remaining SMALLINT NOT NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
served_at TIMESTAMPTZ NULL
```

**Rules**:
- `second_yellow` → total/remaining = 1  
- `straight_red` → total/remaining = 2  
- Active = `matches_remaining > 0` AND `served_at IS NULL`  
- Index: `(club_id)` where active; `(player_card_id)` where active  
- RLS: enable + policies for bot roles (same pattern as other player tables)

## 4. `match_history` extensions (optional columns)

| Column | Type | Notes |
|--------|------|--------|
| `decided_by` | TEXT NULL | `regulation` \| `extra_time` \| `penalties` |
| `home_penalties` | SMALLINT NULL | shootout scored |
| `away_penalties` | SMALLINT NULL | |

`result` remains win/draw/loss from **final** competitive outcome (after pens). Phase 1 rewards still use existing bot policy keyed off that result / run id.

## 5. `game_config` keys

| Key | Default | Purpose |
|-----|---------|---------|
| `competitive_match_enabled` | `false` | master flag |
| `competitive_extra_time_fatigue_multiplier` | `1.35` | ET fatigue |
| `competitive_extra_time_injury_multiplier` | `1.25` | ET injury |
| `bot_dynamic_difficulty_enabled` | `true` | Phase 6 |
| `bot_difficulty_rating_offset` | `0` | |
| `bot_difficulty_min_delta` | `-4` | |
| `bot_difficulty_max_delta` | `4` | |

Env: `COMPETITIVE_MATCH_ENABLED` overrides master flag when set.

## 6. Match result stats extensions (engine payload)

Add to streamed result / finalize digest:

- corners, fouls, offsides (home/away)
- yellow/red counts (home/away)
- `extra_time_played` bool
- pen tallies + `penalty_winner_club_id`

Existing possession/shots/SOT/goals/cards/injuries/ratings/MOTM retained.

## 7. State transitions

```text
[flag off] regulation end → COMPLETE (today)

[flag on] regulation end score≠ → COMPLETE (decided_by=regulation)
[flag on] regulation end score= → EXTRA_TIME_FIRST
  → EXTRA_TIME_SECOND
  → if score≠ COMPLETE (decided_by=extra_time)
  → if score= PENALTY_SHOOTOUT → COMPLETE (decided_by=penalties)

settlement:
  apply existing bot rewards
  upsert suspensions from dismissal consequences
  decrement active suspensions for this club's cards that played / club match served
  write decided_by + pen columns
```

Suspension decrement policy: one eligible completed Bot Battle for the **club** decrements `matches_remaining` for that club’s active suspensions (cards not required to have played while suspended — they were blocked). When remaining hits 0, set `served_at`.
