# Contract: `claim_daily_pack` RPC (Vote Gate Extension)

**Feature**: `025-topgg-vote-pack`  
**Migration**: `069_topgg_vote_pack.sql`

## Signature change

**Drop** old overload:

```sql
DROP FUNCTION IF EXISTS public.claim_daily_pack(BIGINT, JSONB);
```

**Replace** with:

```sql
CREATE OR REPLACE FUNCTION public.claim_daily_pack(
    p_club_id BIGINT,
    p_cards JSONB,
    p_topgg_vote_at TIMESTAMPTZ
) RETURNS JSONB
```

`SECURITY DEFINER`, `search_path = public`. GRANT to `anon`, `authenticated`, `service_role`.

## New column

```sql
ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS last_consumed_topgg_vote_at TIMESTAMPTZ;
```

## Config keys (seeded in migration)

| Key | Default |
|-----|---------|
| `daily_pack_cooldown_hours` | `12` |
| `topgg_vote_bypass_enabled` | `0` |

Cooldown check uses:

```sql
v_cooldown_hours := public.get_game_config_int('daily_pack_cooldown_hours', 12);
-- v_last + (v_cooldown_hours || ' hours')::INTERVAL
```

## Behavior (ordered)

1. Validate `p_cards` non-empty (unchanged).
2. `SELECT last_claim_at, last_consumed_topgg_vote_at FROM players WHERE discord_id = p_club_id FOR UPDATE`.
3. Not found → `'Account not found'`.
4. **Vote timestamp required**: `p_topgg_vote_at IS NULL` → `'VOTE_REQUIRED'`.
5. **Vote freshness**: `p_topgg_vote_at < NOW() - INTERVAL '12 hours'` → `'VOTE_STALE'`.
6. **Vote replay**: `p_topgg_vote_at <= last_consumed_topgg_vote_at` → `'VOTE_ALREADY_USED'`.
7. **Cooldown**: if `last_claim_at + cooldown_hours > NOW()` → `'COOLDOWN:{seconds}'` (unchanged format).
8. `UPDATE players SET last_claim_at = NOW(), last_consumed_topgg_vote_at = p_topgg_vote_at`.
9. Insert cards from `p_cards` (unchanged loop from migration 051).
10. Return `{ "card_ids": [...], "claimed_at": "...", "vote_consumed_at": "..." }`.

## Exception strings (app parsing)

| Substring / exact | Bot action |
|-------------------|------------|
| `COOLDOWN:` | `gacha_cooldown_embed` |
| `VOTE_ALREADY_USED` | `topgg_vote_replay_embed` |
| `VOTE_STALE` | `topgg_vote_prompt_embed` (re-vote) |
| `VOTE_REQUIRED` | Should not occur if bot gates correctly; log + generic error |

## Atomicity

Vote consumption and card insert remain in **one transaction**. Any insert failure rolls back `last_claim_at` and `last_consumed_topgg_vote_at` updates.

## Callers

| Caller | Update |
|--------|--------|
| `apps/discord_bot/cogs/store_cog.py` | Pass `p_topgg_vote_at` from `VoteCheckResult.vote_at` (or `now()` on bypass) |

Grep must show **zero** remaining 2-arg invocations after ship.

## verify_required_schema.sql

Add:

- `column:public.players.last_consumed_topgg_vote_at`
- Update `function:claim_daily_pack` guard to `to_regprocedure('public.claim_daily_pack(bigint,jsonb,timestamptz)')`

## Must not

- Verify Top.gg HTTP inside SQL (bot-only)
- Split vote consumption UPDATE from card INSERT into separate app calls
- Remove `FOR UPDATE` row lock
