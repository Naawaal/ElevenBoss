# Research & UX Audit: Marketplace V1.5 — Professional UX & Polish

**Feature**: `045-marketplace-ux-polish`  
**Date**: 2026-07-24  
**Status**: Pre-plan audit complete — **no implementation in this phase**

This document is the mandatory Phase 1–10 deliverable set: audit, journeys, consistency, IA, pain points, performance, prioritized opportunities, wireframes, and phased plan outline.

---

## 1. Complete Marketplace UX Audit

### 1.1 Screen inventory

| Surface | Entry | Primary file | Notes |
|---------|-------|--------------|-------|
| Hub | `/marketplace` | `apps/discord_bot/cogs/marketplace_cog.py` | Title soup today |
| Search chooser | Hub → Search | `views/marketplace_transfer.py` | P2P on only |
| Board filters | Search → Transfer Board | `marketplace_transfer.py` | Mandatory stage |
| Board results / detail | Apply / select / sort | `marketplace_transfer.py` | Opaque before select |
| Buy confirm | Buy Now | `marketplace_transfer.py` | Followup ephemeral; drops discovery |
| My Listings | Hub | `marketplace_transfer.py` | `expires_at` fetched, unused |
| List player + modal + confirm | My Listings | `marketplace_transfer.py` | Discovery on confirm |
| Agent sell + offer | Hub | `marketplace_cog.py` | POT hidden on offer |
| Regen scouting | Search / shortcut | `marketplace_cog.py` | Separate from academy youth |

**Not marketplace:** `/store`, academy youth scout hub, onboarding flavor copy. **No** dedicated `embeds/*market*` — embeds are inline.

### 1.2 Architecture (keep)

```text
/marketplace (cog)
├── Agent sale → process_agent_sale
├── Search → Transfer Board → purchase_transfer_listing
│         → Regen Scouting → purchase_scouting_player
└── My Listings → create_transfer_listing / cancel
Pure: packages/economy (fair value, sorts, discovery helpers)
DB: 062/075 + 086 intelligence RPCs
```

Reuse views/cog; no new DDD layer; no Discord in `packages/`.

---

## 2. Player journey analysis

| Journey | ~Interactions today | Friction |
|---------|---------------------|----------|
| Browse→buy (P2P on, defaults) | ~8 | Blind select; no time-left; confirm loses discovery |
| Browse→buy (filters+sort) | ~8–12 | Filter stage always |
| List for sale | ~6 | OK; discovery present on confirm |
| Agent sell | ~4 | Thin offer (no POT) |
| Regen scout (P2P on) | ~5 | Extra Search hop |
| Regen scout (P2P off) | ~4 | OK |

**Target journey (polish):**

```text
/marketplace → Search → Transfer Board
  → [optional filters] → Results with scannable preview
  → Select → Detail (fair + discovery + ownership + time)
  → Buy → Confirm (compact context retained) → Success
```

---

## 3. UI consistency review

| Theme | Issue | Polish direction |
|-------|-------|------------------|
| Naming | Marketplace / Global Transfer Market / Search Market / Transfer Board | One primary hub name + labeled sub-areas |
| Back labels | Mixed emoji / wording | One pattern: `Back to Market` |
| Confirms | Followup (buy/list) vs edit (agent/scout) | Prefer consistent ephemeral ownership; don’t break races |
| Colors | Almost all `0x00FF87` | Keep green brand; yellow for money confirms; optional subtle distinction for board vs agent |
| Emoji | Hub heavy, board plain | One policy (hub icons OK; child screens align) |
| Errors | Three ownership phrasings | One shared copy helper |
| Pagination | Silent 25-cap | Optional “Showing up to 25” when truncated |

---

## 4. Information architecture review

**Buy decision stack (priority order):**

1. Ask price + affordability cue (coins known on hub)
2. OVR / role / age / POT / rarity
3. Time remaining
4. Ask vs fair
5. Discovery (avg/median/active/trend + recent sales)
6. Ownership trail
7. Tax/net reminder (once, not every screen)

**Today’s gap:** (3)(4) weak/missing on browse; (5) partial; buy confirm drops (4)(5).

**Do not dump ops analytics** on hub (`get_market_analytics` stays ops-only).

---

## 5. Pain point analysis (mobile manager)

| # | Impact | Pain |
|---|--------|------|
| 1 | High | Blind results list — must open Select to learn anything |
| 2 | High | No time-left despite `expires_at` in query |
| 3 | High | Naming soup |
| 4 | Med | Discovery stripped on Buy confirm |
| 5 | Med | `recent_sales` unused; trend raw |
| 6 | Med | No ask-vs-fair on detail |
| 7 | Med | Agent offer hides POT |
| 8 | Med | Board re-fetch on every select/sort |
| 9 | Low | Emoji / Back inconsistency |
| 10 | Low | Unexplained 25-cap |

---

## 6. Performance review

| Smell | Location | Fix direction |
|-------|----------|---------------|
| Hub `players.select("*")` | `marketplace_cog.py` | Narrow columns |
| Global `active_training` read | cog + transfer views | Scope to owner / known card ids |
| Full roster `select("*")` for sell/list | both | Narrow + reuse |
| Re-fetch board on select/sort | `show_transfer_board` | In-memory sort/select; refresh on Apply / after mutate |
| Detail: discovery + ownership stacked | OK if needed | Keep; don’t add analytics |
| Scouting `select("*")` | cog | Narrow columns |

Settlement RPCs stay authoritative — no caching of purchase results.

---

## 7. Prioritized polish opportunities (impact vs effort)

| ID | Opportunity | Impact | Effort | Story |
|----|-------------|--------|--------|-------|
| P1 | Scannable board preview + time-left | High | Low | US1 |
| P2 | Ask vs fair + rarity on detail | High | Low | US1 |
| P3 | Keep compact discovery on Buy confirm | High | Low | US1/US2 |
| P4 | Render `recent_sales` + readable trend | High | Low | US2 |
| P5 | Unify hub naming + Back labels | Med | Low | US3 |
| P6 | My Listings expiry display | Med | Low | US4 |
| P7 | Agent offer show POT | Med | Low | US4 |
| P8 | In-memory board select/sort (no re-fetch) | Med | Med | US5 |
| P9 | Scope training eligibility query | Med | Low | US5 |
| P10 | Narrow `select` columns | Low | Low | US5 |
| P11 | Shared ownership error copy | Low | Low | US3 |
| P12 | “Showing up to 25” when truncated | Low | Low | US3 |
| — | Favorite filters / recently viewed | Med | Med–High | **Defer** (YAGNI until P1–P10 land) |
| — | True multi-page browse | Med | High | **Out of scope** |
| — | Ops analytics in Discord | Low | Med | **Reject** (043) |

---

## 8. Wireframes (Discord-shaped)

### 8.1 Hub (after)

```text
┌ Marketplace ─────────────────────────┐
│ Transfer Board · Scouting · Agent    │
│ Coins: N                             │
│ Active listings: N  (if P2P)         │
├──────────────────────────────────────┤
│ [Search Market] [Sell to Agent]      │
│ [My Listings]   (if P2P)             │
└──────────────────────────────────────┘
```

### 8.2 Board results (after)

```text
┌ Transfer Board — Results ────────────┐
│ Showing 12 (up to 25) · Sort: Price  │
│                                      │
│ • Ada Mid  78 OVR  2,400🪙  14h left │
│ • Bo Def   74 OVR  1,900🪙  2h left  │
│ …                                    │
│ Tax: sellers net 90% (once)          │
├──────────────────────────────────────┤
│ [Select listing ▼] [Sort ▼]          │
│ [Buy Now] [Back to Market]           │
└──────────────────────────────────────┘
```

### 8.3 Detail + buy confirm (after)

```text
Detail:
  Ada · MID · Rare · 78 OVR · POT 86 · Age 22
  Ask 2,400 · Fair ~2,100 · Ends in 14h
  Market: avg 2,250 · median 2,200 · trend ↓
  Recent: 2,300 · 2,100 · 2,400
  Clubs: ClubA → ClubB → you?

Confirm:
  Buy Ada for 2,400?
  Fair ~2,100 · market soft ↓
  [Confirm] [Cancel]
```

---

## 9. Phased implementation plan (for `/speckit.plan`)

| Phase | Focus | Delivers |
|-------|-------|----------|
| A | Board preview + time-left + ask/fair/rarity | US1 core |
| B | Discovery presentation + buy-confirm context + recent sales | US2 |
| C | Naming / Back / confirm / error copy consistency | US3 |
| D | My Listings expiry + agent POT + success copy | US4 |
| E | In-memory board + scoped training query + narrow selects | US5 |
| F | Playtest checklist + `change_log.md` player note | Ship |

**Principles:** no new mechanics; no analytics-on-hub; no new slash command; prefer editing `marketplace_cog.py` / `marketplace_transfer.py`; cite **US-42.6** on mutating PRs if any RPC touch (prefer zero).

---

## Frozen product decisions (specify)

| ID | Decision |
|----|----------|
| D1 | Polish-only — reuse 017/043 backend |
| D2 | No new slash commands / tables by default |
| D3 | Never invent market numbers |
| D4 | Ops analytics stay out of Discord hub |
| D5 | Favorite filters / recently viewed deferred |
| D6 | Academy youth scout stays out of marketplace scope |
| D7 | Select(25) ceiling remains; optional truncate copy only |

## Next command

`/speckit.plan` — technical plan from this audit + [spec.md](./spec.md).  
Do **not** implement until plan/tasks and owner validation.
)
