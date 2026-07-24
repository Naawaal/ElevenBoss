# Research: Marketplace Intelligence & Market Analytics

**Feature**: `043-marketplace-intelligence` | **Date**: 2026-07-24  
**Companion**: [spec.md](./spec.md) · [plan.md](./plan.md)

---

## 1. Current-state findings (workspace audit)

### 1.1 What already exists

| Capability | Location | Notes |
|------------|----------|-------|
| P2P list/cancel/buy | `062` RPCs + `marketplace_transfer.py` | Buy-it-now; tax 10%; flag default off |
| Sale audit | `transfer_sales_log` | listing/seller/buyer/card/gross/tax/net/created_at only |
| Listing lifecycle | `transfer_listings` | active/sold/cancelled/expired retained |
| Fair value guide | `compute_agent_offer` / `generate_agent_offer` | Used at list time; **not** stored on sale |
| Coin audit | `economy_ledger` | `transfer_buy`, `transfer_sale`, `agent_sale`, scouting sources |
| Agent daily cap | `agent_sale_daily_log` | Counts only |
| Board filters | Position + OVR/age/POT bands | Fetch ≤50, filter in app, ≤25 selects |
| Board sort | Newest-ish (`created_at desc` on fetch) | No manager sort control |
| Ownership trail | — | Only live `player_cards.owner_id` |
| Price discovery UI | — | Absent |
| Market analytics UI | — | Ops can sum tax via registry docs only |

### 1.2 Gaps vs spec

1. Sale log lacks attribute/fair-value snapshots → cannot power discovery/analytics safely after card changes.  
2. No ownership career table → trail cannot survive agent DELETE.  
3. No cohort read model / insufficient-data gate.  
4. No sort modes / Best Value.  
5. No packaged ops analytics RPC.

### 1.3 Duplicate / debt notes

- Fair value duplicated Python ↔ SQL (`generate_agent_offer` / `compute_agent_offer`) — snapshot must use **SQL** value inside purchase for authority.  
- `075` recreate of `create_transfer_listing` may omit payroll assert on fresh migrate — out of scope to fix unless we REPLACE that function; bot still gates.  
- Board bound (50/25) is Discord-honest; sorts must not claim global infinite ranking.

---

## 2. Decisions

### D1 — Enrich `transfer_sales_log` (no parallel history table)

- **Decision**: ALTER existing append-only sales log; extend purchase INSERT.  
- **Rationale**: Already UNIQUE per listing, used for relist cooldown, RLS present, tax observability documented.  
- **Alternatives**: New `transfer_history` table (rejected — duplicate SoT); ledger-only reconstruction (rejected — missing snapshots).

### D2 — Snapshot columns at sale

- **Decision**: Store `fair_value_coins`, `rarity`, `role`, `overall`, `potential`, `age_at_sale`, `player_name` on each new sales log row.  
- **Rationale**: Spec FR-001; card mutates after sale; discovery must use sale-time facts.  
- **Alternatives**: Join live `player_cards` at query time (rejected — wrong after train/age/agent delete).

### D3 — `card_ownership_history` without CASCADE delete

- **Decision**: New table; `card_id UUID NOT NULL` with **no FK** to `player_cards` (same pattern as sales log `card_id`); `owner_id` → `players` ON DELETE SET NULL; snapshot `club_name` at segment open.  
- **Rationale**: Agent sale `DELETE`s cards; career must survive (spec edge case).  
- **Alternatives**: FK ON DELETE CASCADE (rejected — wipes history); soft-delete cards instead of DELETE (rejected — out of scope / changes agent rail).

### D4 — Write ownership inside purchase + close on agent sale

- **Decision**: In `purchase_transfer_listing`, after ownership UPDATE: close open seller segment (`ended_at`, link sales log id), open buyer segment (`acquired_via='p2p_transfer'`). In `process_agent_sale`, before DELETE: close open segment (`acquired_via` end reason / `ended_via='agent_sale'`).  
- **Rationale**: Same transaction as money + owner move → SC-001.  
- **Alternatives**: Async bot-side second write (rejected — can diverge); triggers on `owner_id` (rejected — harder to reason, pack noise).

### D5 — Lazy bootstrap + selective acquisition wiring

- **Decision**: RPC/helper `ensure_card_ownership_open(card_id, owner_id, via)` used by career UI when no rows; wire `purchase_scouting_player` / `sign_youth_scout_prospect` opens in **086** if REPLACE is already required; **do not** patch every pack INSERT in this feature.  
- **Rationale**: Spec allows deferring pack hooks; YAGNI / ponytail — full acquisition coverage is a follow-up.  
- **Alternatives**: Patch all INSERT sites now (rejected — large blast radius for little early ROI).

### D6 — Cohort definition

- **Decision**: Same `role` + `rarity`; `overall` within ± window (config default **3**); completed P2P sales with non-null snapshots only; min count config default **5**.  
- **Rationale**: Spec FR-008 / Assumptions.  
- **Alternatives**: OVR-only bands (weaker similarity); exact OVR match (too cold).

### D7 — Trend window

- **Decision**: Median of cohort sales in last 7 UTC days vs prior 7 days → `up` / `down` / `flat` (flat if equal); omit trend if either window has zero sales.  
- **Rationale**: Simple, explainable, no invented forecast.  
- **Alternatives**: Linear regression (overkill); WoW mean only (median more robust to outliers).

### D8 — Board sorts in-app

- **Decision**: After existing filter pass, sort the in-memory list; Discord select still ≤25. Modes: lowest/highest price, highest OVR/POT, newest (`created_at`), ending soon (`expires_at`), best value (`price/fair`). Missing fair → sort last for Best Value.  
- **Rationale**: Avoids new board queries per sort; matches current fetch pattern.  
- **Alternatives**: Server-side ORDER BY with pagination tokens (future; not required for 50-row bound).

### D9 — Ops analytics RPC, not Discord admin hub

- **Decision**: `get_market_analytics(p_from timestamptz, p_to timestamptz) → jsonb` aggregating listings + sales log + agent ledger counts; document in quickstart. No player-facing analytics dashboard.  
- **Rationale**: Spec US5 / FR-011 “internal”; YAGNI.  
- **Alternatives**: Materialized `market_daily_stats` + nightly job (defer until slow); Discord admin embed (scope creep).

### D10 — Migration 086, preserve market economics

- **Decision**: New numbered migration only; do not change tax bps, floor/ceil, TTL, slot cap, or flag default.  
- **Rationale**: Intelligence layer observes; does not rebalance.  
- **Alternatives**: Bundle with economy retune (rejected — separate concern).

### D11 — Forward-only enrichment

- **Decision**: Existing sales log rows get NULL new columns; discovery/analytics skip incomplete snapshot rows for cohort attribute filters; money totals still count all rows.  
- **Rationale**: Honest history; no guessed backfill.  
- **Alternatives**: Backfill from current card stats (rejected — wrong after mutations/deletes).

---

## 3. Performance notes

| Path | Approach |
|------|----------|
| Purchase | Extra SELECT of card attrs + 2 ownership writes inside existing txn — acceptable |
| Board + sort | No extra DB round-trip vs today |
| Price discovery | Single RPC using indexes on `(role, rarity, overall, created_at)` / time |
| Analytics | Ops-invoked; not on hub open; indexes on `created_at`, listing status |

Indexes to add (see data-model): sales log by time; by card; cohort helper index; ownership by card; open-segment unique partial.

---

## 4. Integrity / future compatibility

- Preserves US-42.6: one winner, own-buy block, tax burn, buy-it-now only.  
- Append-only sales + ownership segments support future weekly reports / career timelines / featured listings without redesign.  
- Do **not** implement dynamic demand or featured listings now.

---

## 5. Resolved clarifications

No open NEEDS CLARIFICATION from Technical Context — defaults frozen in D1–D11 and spec Assumptions.
)
