# Research: Top.gg Vote Gate for Store Free Pack

**Feature**: `025-topgg-vote-pack`  
**Date**: 2026-07-21

## Current State Inventory

### Store / free pack flow (exists today)

| Component | Location | Behavior |
|-----------|----------|----------|
| Entry | `/store` slash command | `StoreCog.store` → defer → `show_store()` |
| Hub view | `apps/discord_bot/cogs/store_cog.py` → `StoreHubView` | Ephemeral embed + buttons; **not** registered in `main.py` (session-scoped, not persistent) |
| Pack button | `custom_id="store_gacha_claim"`, label **🎫 Claim Free Pack** | Disabled when `gacha_ready=False` (22h cooldown) |
| Cooldown UI | `show_store()` reads `players.last_claim_at` | Client-side preview; server enforces in RPC |
| Pack generation | `gacha.generate_pack(n=5)` + optional `get_pack_rarity_override(db)` | Bot-side before RPC |
| Atomic claim | RPC `claim_daily_pack(p_club_id, p_cards)` | 22h gate, `FOR UPDATE`, inserts cards, sets `last_claim_at` |
| Success embed | `gacha_claim_embed(pack)` | 5-card reveal |
| Cooldown embed | `gacha_cooldown_embed(remaining_seconds)` | On `COOLDOWN:` exception from RPC |

### Database (exists today)

- `players.last_claim_at TIMESTAMPTZ` — pack cooldown anchor (22 hours in RPC)
- **No** Top.gg vote columns or vote-consumption log table
- **No** migration/RPC changes for external vote verification

### Configuration / secrets (exists today)

- `.env.example` has Discord + Supabase only — **no** `TOPGG_TOKEN`, **no** bot listing URL
- `game_config` has pack odds keys (024) but nothing vote-related

### Top.gg integration (does NOT exist)

- Grep across repo: zero vote/topgg code in `apps/` or `packages/`
- `specs/008-public-website` mentions Top.gg only as a future external link, not bot vote API

### Related SDD (baseline behavior)

- `.specify/specs/v1.0.0/spec.md` **US-02**: free pack every **22 hours**, no external requirement
- `change_log.md`: atomic claim fix — failed insert no longer burns cooldown (RPC-level)

---

## Top.gg API Options

### Recommended: v1 vote check (current API)

```
GET https://top.gg/api/v1/projects/@me/votes/{discord_user_id}?source=discord
Authorization: Bearer {TOPGG_TOKEN}
```

**Active vote**: response includes vote metadata; `nextVoteAt` (or equivalent) is in the future → user voted within the current window.

**No / expired vote**: `404 Not Found`.

**Rate limit**: documented ~60 req/min on legacy v0; v1 follows platform limits — cache per-user checks briefly during a single claim interaction only.

### Legacy fallback: v0 check (still supported)

```
GET https://top.gg/api/bots/{bot_id}/check?userId={discord_user_id}
Authorization: {TOPGG_TOKEN}
```

Returns `{ "voted": 1 | 0 }` where `1` = voted in past **12 hours**.

**Decision for v1 spec**: Prefer **v1** endpoint; v0 acceptable as documented fallback if v1 token format differs in ops environment. Both use 12-hour vote windows aligned with Top.gg platform rules.

### Vote URL (user-facing)

Standard pattern: `https://top.gg/bot/{application_id}/vote`  
Bot application ID = Discord snowflake (available at runtime via `bot.user.id` or `DISCORD_APPLICATION_ID` env).

---

## Design Constraints (from AGENTS.md)

| Rule | Implication |
|------|-------------|
| No new slash command | Extend `StoreHubView.gacha_claim_btn` only |
| Monorepo | Top.gg HTTP client lives in `apps/discord_bot/core/` — **not** `packages/` (external IO) |
| DB via RPC | Vote consumption + claim stay atomic; extend `claim_daily_pack` or add companion RPC |
| Schema Rule | New columns/tables → new numbered migration + `verify_required_schema.sql` |
| Defer first | Button handler already defers — keep pattern |

---

## Open Decisions (resolved in spec assumptions)

1. **Pack cooldown vs vote window**: Align pack cooldown to **12 hours** (Top.gg vote cycle) or keep **22 hours**?  
   → Spec default: **12 hours** for both vote validity and pack cooldown (single window). Ops can tune via `game_config` if needed later.

2. **API downtime policy**: Fail open (allow claim) vs fail closed (block with retry message)?  
   → Spec default: **fail closed** with friendly retry copy; optional `game_config` bypass flag for ops emergencies only (not default on).

3. **Vote consumption tracking**: Trust Top.gg timestamp only vs persist consumed vote id?  
   → Spec default: persist `players.last_vote_consumed_at` (or vote cycle id) in same RPC as claim to prevent replay if user clicks twice quickly while API still shows active vote.

---

## Files Expected to Change (implementation preview — not in specify phase)

| File | Change |
|------|--------|
| `apps/discord_bot/cogs/store_cog.py` | Vote check before pack gen; button label/copy; vote prompt embed |
| `apps/discord_bot/core/topgg_vote.py` (new) | HTTP client + typed result |
| `apps/discord_bot/embeds/gacha_embeds.py` | Vote-required / API-unavailable embeds |
| `supabase/migrations/0NN_topgg_vote_pack.sql` | Optional vote-consumption column + RPC gate |
| `.env.example` | `TOPGG_TOKEN` |
| `.specify/specs/v1.0.0/spec.md` | US-02 acceptance criteria |
| `change_log.md` | Player-facing note |
