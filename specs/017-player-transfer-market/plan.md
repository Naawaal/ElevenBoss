# Implementation Plan: Player-to-Player Transfer Market

**Branch**: `017-player-transfer-market` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-player-transfer-market/spec.md`

## Summary

Add a **global buy-it-now** player-to-player board on `/marketplace` beside existing agent sales and regen scouting. Sellers list eligible roster cards at custom prices within fair-value bounds; buyers filter by position / OVR / age / potential and purchase instantly. On sale, buyer pays full listed price; seller receives **90%**; **10%** leaves the economy (tax sink). Feature-flagged off by default so current hub behavior is unchanged until rollout.

**Technical approach**: New migration `062_p2p_transfer_market.sql` — `transfer_listings` + `transfer_sales_log`, `game_config` knobs, atomic RPCs (`create` / `cancel` / `purchase` / `expire`). Coins only via `apply_club_economy`. Cards move by **`UPDATE player_cards.owner_id`** (preserve XP/fatigue/identity). Pure tax/bounds helpers in `packages/economy`. Extend `marketplace_cog` only (no new slash command). Hourly sweeper expires stale listings.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, existing `economy` package + `apply_club_economy`

**Storage**: Supabase — new tables `transfer_listings`, `transfer_sales_log`; `game_config` keys; RLS in same migration; extend `verify_required_schema.sql`

**Testing**: pytest for pure tax/bounds/filter helpers; RPC race / tax assertions via local DB or mock where patterns already exist; Discord smoke via quickstart

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (packages + discord_bot + migrations)

**Performance Goals**: Board browse ≤25 rows per Discord select page; purchase RPC single-transaction under Discord defer window; expiry batch set-based

**Constraints**: AGENTS.md / constitution — no `discord` in `packages/`; no coin/XP bypasses; columns/RPCs only via new migration (never edit applied ones); defer interactions immediately; no new slash command; RLS + schema guard; YAGNI — no auctions

**Scale/Scope**: 1 migration; ~1 economy helper module; marketplace cog/views extension; 1 scheduler job; feature flag default **false**

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Tax/bounds/filter pure logic in `packages/economy`; Discord views only in `apps/discord_bot/` |
| II. DB via RPC | PASS | List/cancel/buy/expire atomic RPCs; all coins via `apply_club_economy` |
| III. Typing / Pydantic | PASS | Typed helpers + result models at package boundary |
| IV. Slash + defer | PASS | Extend `/marketplace` only; defer before RPC |
| V. APScheduler | PASS | Expiry sweeper for listing TTL |
| VI. Friendly errors | PASS | Map RPC exceptions to ephemeral embeds |
| VII. YAGNI | PASS | Buy-it-now only; agent+scouting untouched; no private offers / swaps |

**Post-Phase 1 re-check**: PASS — contracts use ownership transfer + implicit tax burn (buyer −gross / seller +net); no system sink club; flag + existing rails preserved.

## Project Structure

### Documentation (this feature)

```text
specs/017-player-transfer-market/
├── plan.md                 # This file
├── research.md             # Phase 0 (assessment + decision freeze)
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── transfer-tax-bounds.md
│   ├── create-cancel-listing.md
│   ├── purchase-transfer-listing.md
│   ├── expire-listings.md
│   └── marketplace-p2p-ui.md
└── tasks.md                # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
supabase/migrations/062_p2p_transfer_market.sql
supabase/scripts/verify_required_schema.sql          # extend guards
scratch/apply_migration_062.py

packages/economy/economy/transfer_market.py          # NEW — tax net, price bounds, fair-value guide
packages/economy/economy/flows.py                    # optional EconomyConfig mirrors for defaults
packages/economy/economy/__init__.py                 # exports
packages/economy/economy/engine.py                   # reuse generate_agent_offer as fair-value base

apps/discord_bot/cogs/marketplace_cog.py             # hub flag, Transfer Board, My Listings, list/buy/cancel
apps/discord_bot/views/marketplace_transfer.py       # NEW — optional split if cog grows
apps/discord_bot/tasks/transfer_listing_expiry_job.py # NEW — call expire_stale_transfer_listings
apps/discord_bot/core/scheduler_jobs.py              # wire hourly (or cron) expiry
apps/discord_bot/main.py                             # register job
apps/discord_bot/cogs/development_cog.py             # exclude transfer-listed cards from drill/fusion targets
apps/discord_bot/cogs/squad_cog.py                   # reject assign of listed cards (belt + RPC)

tests/test_transfer_market_math.py                   # NEW — tax, floor/ceil, net preview

change_log.md                                        # on implement ship
.specify/specs/v1.0.0/spec.md                        # reconcile US-11 on implement
```

**Structure Decision**: Extend the existing marketplace + economy monorepo layout; do not add apps or packages.

## Complexity Tracking

> No constitution violations requiring justification.

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research + decisions | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Frozen implementation decisions (from research)

| ID | Decision |
|----|----------|
| D1 | Buy-it-now only |
| D2 | Tax 10% = seller net 90%; burn by never crediting tax portion |
| D3 | Card moves via `UPDATE owner_id` (not delete+reinsert) |
| D4 | Price floor **0.75×** / ceiling **2.5×** `compute_agent_offer` / `generate_agent_offer` |
| D5 | Listing TTL **72h**; sweeper expires → cancel-equivalent return |
| D6 | Relist cooldown **6h** after P2P acquire (sales_log check) |
| D7 | Slot cap **5**; flag `p2p_transfer_market_enabled` default **false** |
| D8 | Agent + scouting rails unchanged |
| D9 | Buyer must have senior roster room (`senior_roster_cap`, exclude academy/retired; listed cards still count for seller until sold) |
| D10 | Migration **062**; extend schema verify + RLS in same file |

## Next command

`/speckit.tasks` — break this plan into implementation tasks.
