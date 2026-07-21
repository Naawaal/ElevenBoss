# Data Model: Top.gg Vote Gate for Free Store Pack

**Feature**: `025-topgg-vote-pack`

## Entities

### `players` (extended)

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `last_claim_at` | `TIMESTAMPTZ` | NULL | Pack cooldown anchor (unchanged column; interval changes to 12h default) |
| `last_consumed_topgg_vote_at` | `TIMESTAMPTZ` | NULL | **NEW** — Top.gg vote timestamp consumed by last successful pack claim |

**Relationships**: One row per club (`discord_id` PK). No new tables.

### `game_config` keys (new)

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `daily_pack_cooldown_hours` | int | `12` | Pack claim cooldown (was hardcoded 22h in RPC) |
| `topgg_vote_bypass_enabled` | int | `0` | Ops emergency: `1` skips Top.gg API in bot (default off) |

Existing pack odds keys (`pack_standard_rarities`, etc.) — **unchanged**.

### External: Top.gg vote status (not persisted except consumption marker)

| Field (API) | Usage |
|-------------|-------|
| `votedAt` / vote timestamp | Passed to RPC as `p_topgg_vote_at`; stored in `last_consumed_topgg_vote_at` on success |
| `nextVoteAt` | Bot validates `now() < nextVoteAt` ⇒ active vote window |

## Validation rules

### Bot layer (before RPC)

1. If `topgg_vote_bypass_enabled != 1`: Top.gg API must return active vote.
2. `TOPGG_TOKEN` must be non-empty for verification (else `unavailable`).
3. Vote timestamp extracted from API must parse as UTC `TIMESTAMPTZ`.

### RPC `claim_daily_pack`

1. `p_cards` non-empty JSON array (unchanged).
2. `p_topgg_vote_at` NOT NULL (required in v1 — bypass skips bot API but still passes `now()` at bypass path **or** RPC accepts NULL only when bypass — **decision**: bypass path passes `NOW()` at UTC; RPC always requires non-null timestamp).
3. `p_topgg_vote_at >= NOW() - INTERVAL '12 hours'` → else `VOTE_STALE`.
4. `p_topgg_vote_at > COALESCE(last_consumed_topgg_vote_at, '-infinity')` → else `VOTE_ALREADY_USED`.
5. `last_claim_at + daily_pack_cooldown_hours` elapsed → else `COOLDOWN:{seconds}`.
6. On success: set `last_claim_at = NOW()`, `last_consumed_topgg_vote_at = p_topgg_vote_at`, insert cards.

## State transitions

```text
[eligible] ──(no recent vote)──► vote prompt (no DB write)
[eligible] ──(voted, RPC ok)──► [on cooldown] + cards inserted + vote consumed
[on cooldown] ──(click)──► COOLDOWN embed
[voted, same vote_at replay] ──► VOTE_ALREADY_USED (even if cooldown elapsed but Top.gg hasn't reset)
[eligible] ──(new vote_at > last_consumed) + cooldown ok ──► claim success
```

## Indexes

None required — lookups by `discord_id` PK with `FOR UPDATE` (existing pattern).

## RLS

No new exposed tables — `players` RLS unchanged (bot uses service role).
