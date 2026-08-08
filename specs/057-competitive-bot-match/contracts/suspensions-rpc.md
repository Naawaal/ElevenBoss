# Contract: Player Suspensions RPC

**Feature**: `057-competitive-bot-match`  
**Migration**: `109_competitive_bot_match.sql`

## Table

`public.player_suspensions` — see data-model.md. RLS + policies for anon/authenticated/service_role as required by bot Data API usage.

## Settlement extension (atomic)

Extend existing bot settlement path (same transaction as XP/economy marks or a single SECURITY DEFINER RPC called once per run), e.g.:

```text
apply_bot_match_discipline(
  p_run_id UUID,
  p_club_id BIGINT,
  p_dismissals JSONB  -- [{player_card_id, reason: second_yellow|straight_red}]
) RETURNS JSONB
```

Behavior:

1. Idempotent on `p_run_id` (second call no-ops creates).
2. For each dismissal: insert suspension with matches_total/remaining 1 or 2.
3. Decrement `matches_remaining` by 1 for all **active** suspensions of `p_club_id` (this Bot Battle serves time).
4. When remaining hits 0: set `served_at = now()`.
5. Never loop from Python with N round-trips.

## Eligibility read

```text
list_active_suspensions(p_club_id) → card ids with matches_remaining > 0
```

Consumed by `squad_validity` / `execute_bot_battle` before kickoff — block those cards with clear ephemeral reason via existing XI validation messaging pattern.

## Schema guard

Add to `verify_required_schema.sql`:
- `table:public.player_suspensions`
- policies
- settlement/list function names as shipped
