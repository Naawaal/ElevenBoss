# Research: Player-to-Player Transfer Market (Pre-Integration Assessment)

**Feature**: `017-player-transfer-market` | **Date**: 2026-07-14  
**Purpose**: Audit current `/marketplace`, competitive FCM patterns, PM/economy stance, and a Discord-fit design blueprint before planning/implementation.  
**Companion**: [spec.md](./spec.md)

---

## 1. Audit — current `/marketplace`

### 1.1 What exists today

| Rail | UI entry | Behavior | Status |
|------|----------|----------|--------|
| Hub | `/marketplace` | Balance (coins + tokens), placeholder **Active Listings `0 / 5`**, buttons Sell / Search / My Listings | Live |
| Agent sell | **Sell Player** | Roster dropdown → `generate_agent_offer` preview → `process_agent_sale` | Live |
| Scouting buy | **Search Market** | Unclaimed `scouting_pool_players` → `purchase_scouting_player` | Live |
| P2P listings | **My Listings (Soon)** | Button **disabled** | Stub only |

**Source**: `apps/discord_bot/cogs/marketplace_cog.py`, US-11 in `.specify/specs/v1.0.0/spec.md`.

There is **no** player-owned listing table. Historical `transfer_market` was dropped in `001_initial_schema.sql`. “Global Transfer Market” naming is aspirational; reality is **NPC agent faucet + regen signing sink**.

### 1.2 Agent sale transaction path

```text
UI: eligible card → generate_agent_offer(OVR, rarity, age, POT)
RPC: process_agent_sale(p_club_id, p_card_id)
  → assert_not_in_match
  → agent_sale_daily_log count ≤ agent_sale_daily_cap (default 10)
  → lock card; reject XI / training / active evo / retired
  → compute_agent_offer (server; client price ignored)
  → DELETE player_cards
  → apply_club_economy(+coins, reason agent_sale, idempotency agent_sale:{card_id})
```

**Pricing (Python mirror)** — `packages/economy/economy/engine.py`:

```text
((OVR-45)^2.5 * 1.5 + 50) * rarity_mult * age_factor * pot_bonus
rarity: Common 1.0 / Rare 1.5 / Epic 2.2 / Legendary 3.5
age: <23 → 1.2; ≤28 → 1.0; ≤32 → 0.8; else 0.5
```

**Guards (cog + RPC)**: Starting XI, active evolution, active training, injured/hospitalized (cog), academy (`in_academy` filtered in sell list), match lock, daily cap.

### 1.3 Scouting buy path

```text
scouting_pool_players (regen inserts on retirement / aging)
list_price ≈ 1.4 × agent valuation (scouting_purchase_price)
RPC: purchase_scouting_player → apply_club_economy(-price, scouting_signing) → insert player_cards → claim row
```

Cap on unclaimed pool: `scouting_pool_max_active` (50). Coins leave buyer; **no seller credit** (system list).

### 1.4 Coin sinks & faucets (economy context)

| Direction | Examples | Notes |
|-----------|----------|-------|
| **Faucets** | Match coins, daily login, agent sales, level rewards | Agent sale is a **major liquid faucet** for surplus cards |
| **Sinks** | Drills, fusion (`fusion_coins`), energy refill, scouting signings, league fees | Scouting is the only market-shaped sink today |
| **Tax** | **None** on agent/scouting | No transfer tax exists |

P2P without a tax would **recirculate** coins 1:1 between clubs (neutral) while concentrating talent; **tax is required** for a true sink. Agent sales still inject coins unless later retuned.

### 1.5 Schema touchpoints today

| Object | Role |
|--------|------|
| `players.coins` (+ ledger via `apply_club_economy`) | Club finance |
| `player_cards` | Inventory; deleted on agent sale |
| `agent_sale_daily_log` | Cap |
| `scouting_pool_players` | Regen listings |
| `game_config` | `agent_sale_daily_cap`, scouting caps, economy keys |
| `squad_assignments`, `active_training`, `active_evolutions` | Sell/list eligibility |

**Gap for P2P**: no `transfer_listings` (or equivalent), no sale history for P2P, hub listing count hard-coded `0`.

### 1.6 Integration risks

- Hub already promises **5 listing slots** — align product with that default.
- Must **not** bypass `apply_club_economy` / invent direct `players.coins` updates (AGENTS §7 Economy).
- Listed cards must stay out of XI / drills / fusion / agent sale / academy paths.
- Feature flag required so scouting + agent do not regress during rollout.

---

## 2. Competitive research (FCM platforms)

### 2.1 EA Sports FC / Ultimate Team Transfer Market

Sources: [FIFPlay FC 26 Transfer Market](https://www.fifplay.com/fc-26-transfer-market/), [FUTwiz tax calculator](https://www.futwiz.com/tax-calculator), [FIFAUTEAM tax explainer](https://fifauteam.com/fc-26-tax-calculator/).

| Pattern | FUT practice | Discord-bot takeaway |
|---------|--------------|----------------------|
| Listing model | Auction (start price) + optional Buy Now; duration 1–12h | **Buy Now only** — Discord cannot host sniping well |
| Search | Deep filters (rating, chemistry, play styles, etc.) | Ship **position / OVR / age / POT** only |
| Tax | **5%** EA tax on completed sales (permanent coin sink) | Spec: **10%** (stronger sink; Discord meta is thinner) |
| Price discovery | Compare Price / live market depth | Show **agent fair-value guide** + floor/ceiling |
| Complexity | High (trading meta, sniping) | Reject FUT auction complexity |

### 2.2 Top Eleven

Sources: [Top Eleven Auctions](https://www.topeleven.com/auctions-and-bidding/), [Nordeus Help — auction timing](https://nordeus.helpshift.com/hc/en/3-top-eleven-be-a-soccer-manager/faq/650-how-auction-works-and-what-s-the-best-time-for-a-bid/), [forum auction redesign](https://forum.topeleven.com/top-eleven-general-discussion/47868-%5Bofficial%5D-new-auctions-tutorial-changes-new-features.html).

| Pattern | Practice | Takeaway |
|---------|----------|----------|
| Live auctions | ~4 min timer; last-10s extensions | **Poor fit** for ephemeral Discord views |
| Filters | Strong filter UX in Transfers menu | Mimic filter *intent*, not live bidding |
| Soft currency mix | Cash + tokens; level-scaled prices | Keep **coins-only** P2P for clarity |

### 2.3 Online Soccer Manager (OSM)

Sources: [OSM Helper guideline](https://osmhelper.com/guideline/), [OSMGuide tips](https://www.osmguide.com/tips/), OSM transferlist forums.

| Pattern | Practice | Takeaway |
|---------|----------|----------|
| Concurrent listings | Typically **4** (events up to 6) | Align with our **5** slot stub |
| Price bounds | ~0.75×–2.5× player value | **Require floor/ceiling** vs agent valuation |
| Buy path | System buyers + player purchases; price decays over sims | We need **human buyers**; optional listing expiry instead of NPC price decay |
| Instant sell | Pay premium currency for instant value | Our **agent sale** already fills this role |

### 2.4 Football Manager (online / browser variants)

Sources: [Football Manager Online-style transfer help](https://www.footballmanager-online.co.uk/help/transfer.html), multiplayer community rulebooks (e.g. Top 100).

| Pattern | Practice | Takeaway |
|---------|----------|----------|
| Fees | Often **~10% agent cut** of transfer fee | Validates **10% tax** product choice |
| Negotiation | Offers, contract demands, delays | **Too heavy** for Discord v1 |
| Anti-collusion | Public bids, fee caps, admin review | Soft rules: floors, cooldowns; no trust-admin market |

### 2.5 Best-practice distillation for ElevenBoss

1. **Buy-it-now only** (reject FUT/Top Eleven auctions for Discord).
2. **Mandatory tax sink** (FUT 5% / FM-like 10% → we choose **10%**).
3. **Price bounds** around fair value (OSM) to stop 1-coin alt dumps.
4. **Listing slot cap** (OSM/FUT inventory pressure).
5. **Coexist with quick-sell NPC** (OSM instant sell ≈ our agent).
6. **Shallow filters** that match pack/regen decisions (position, OVR, age, POT).
7. **Feature flag + keep scouting** so regen sink is not confused with human board.

---

## 3. User & Product Manager perspectives

### 3.1 Manager personas

**Seller (duplicate clearer)**  
Wants: price above agent offer when demand exists; clear net-after-tax; cancel if no interest; list in &lt;2 minutes on phone.

**Buyer (bargain hunter / gap filler)**  
Wants: filter to “MID 70–78 under 24,” trust instant buy won’t race-soft, see enough info to decide without a web app.

**Daily engagement hooks**  
- Pack/academy duplicates → list same day  
- Scouting empty → check human board  
- Matchday gap → quick filter buy  

### 3.2 PM / economy constraints

| Risk | Mitigation in spec |
|------|--------------------|
| Inflation from recirculation | 10% tax per completed P2P sale |
| Alt coin transfers | Price floors + re-list cooldown; reject self-buy |
| Price manip / wash trades | Floors/ceilings; daily listing/purchase soft caps (plan) |
| Card duplication | Atomic RPC; row lock on listing |
| Inventory stuck | Cancel + optional expiry return |
| Complexity | No auctions; extend `/marketplace` only |
| Rollout blast radius | Feature flag; agent + scouting unchanged |

**Retention vs inflation**: Tax sinks coins on every successful human trade; agent sales remain a controlled faucet (daily cap). Prefer slightly “harsh” tax over free recirculation.

---

## 4. Design blueprint (product + technical sketch)

> Spec owns WHAT. This section is the planning seed (HOW sketch). Confirm in `/speckit.plan` against migrations & constitution.

### 4.1 Product rails on `/marketplace`

```text
🏪 Marketplace Hub
├── 💰 Sell to Agent          (existing — instant NPC)
├── 🔍 Search Market
│   ├── 🌱 Regen Scouting     (existing)
│   └── 🔁 Transfer Board     (NEW — P2P, flag-gated)
├── 📋 My Listings            (NEW — enable when flag on)
└── Balance + Active Listings n/max
```

### 4.2 UX wireframes (text)

**Hub**

```text
🏪 Global Transfer Market
Balance: 🪙 12,450 | 🎟️ 2
Active Listings: 2 / 5

[💰 Sell to Agent]  [🔍 Search Market]  [📋 My Listings]
```

**List flow**

```text
📋 List Player
Select card → Fair value guide 🪙 1,200
Price (bounds 🪙 800–3,000): [____]
You receive on sale: 🪙 90% of listed
[Confirm List]  [⬅️ Back]
```

**Transfer Board**

```text
🔁 Transfer Board
Filters: Pos [MID▾] OVR [70–80] Age [≤25] POT [≥82]
Results (page 1/3):
  Luka M. · MID · 74 OVR · 22y · POT 86 · 🪙 2,100
[Select…] [Buy Now 🪙 2,100] [⬅️ Back]
Tax note on confirm: “Seller nets 90%; 10% market tax.”
```

**My Listings**

```text
📋 My Listings (2/5)
Name · OVR · Listed · Net if sold · [Cancel]
```

### 4.3 Schema sketch (migration-owned)

```text
transfer_listings
  id, seller_id, card_id UNIQUE among active,
  price_coins, status (active|sold|cancelled|expired),
  created_at, expires_at, sold_at, buyer_id NULL

transfer_sales_log (or economy ledger metadata)
  listing_id, seller_id, buyer_id, card_id,
  gross_price, tax_amount, seller_net, created_at

game_config keys
  p2p_transfer_market_enabled (bool)
  transfer_listing_slot_cap (5)
  transfer_tax_bps (1000 = 10%)
  transfer_price_floor_mult / transfer_price_ceil_mult
  transfer_listing_ttl_hours
  transfer_relist_cooldown_hours
```

RLS + policies in the **same** migration; extend `verify_required_schema.sql`.

### 4.4 RPC sketch

| RPC | Responsibility |
|-----|----------------|
| `create_transfer_listing(seller, card, price)` | Eligibility, slots, bounds, lock card state, insert listing |
| `cancel_transfer_listing(seller, listing_id)` | Restore card availability |
| `purchase_transfer_listing(buyer, listing_id, expected_price)` | FOR UPDATE listing; debit buyer full price; credit seller 90%; ledger tax sink; `owner_id` transfer; close listing |
| `expire_stale_transfer_listings()` | Sweeper job returns cards |

All coin paths via `apply_club_economy` (reasons e.g. `transfer_buy`, `transfer_sale`, `transfer_tax`). Tax may be implemented as buyer debit = price, seller credit = net, with tax either burned via ledger reason or credited to a null/sink account — plan must pick one consistent pattern matching existing ledger semantics.

**Card movement**: Prefer **ownership transfer** (`UPDATE owner_id`) over delete+reinsert to preserve XP, fatigue, DOB, evolution history. Confirm in plan vs agent-sale delete semantics.

### 4.5 Packages / Discord wiring

| Layer | Work |
|-------|------|
| `packages/economy` | Pure helpers: tax net, price bounds, filter validation |
| `apps/discord_bot/cogs/marketplace_cog.py` | Enable My Listings; Search submenu; list/buy views; defer always |
| Scheduler | Expiry sweeper if TTL used |
| Tests | Bounds, tax math, race purchase, flag off |

### 4.6 Feature flag & rollout

1. Ship migration + RPCs behind `p2p_transfer_market_enabled = false`.
2. Verify schema; bot builds tolerate flag off (current UX).
3. Enable in staging guild → smoke list/buy/cancel/race.
4. Soft launch flag on production; monitor coin sink volume and support tickets.
5. Optionally tighten floors / raise tax via `game_config` without code push.

### 4.7 Open plan decisions — **resolved in `/speckit.plan`**

See §6 Phase 0 decision log below. Soft daily purchase/list caps beyond slot cap: **deferred (YAGNI)** — slot cap + tax + cooldown suffice for v1.

---

## 5. Decision freeze (product — specify)

| ID | Decision |
|----|----------|
| D1 | Buy-it-now only; no auctions |
| D2 | 10% seller-side tax sink |
| D3 | Agent + scouting remain; P2P additive |
| D4 | Feature flag default off |
| D5 | Price bounds from agent fair-value guide |
| D6 | Global market (Discord user / club identity) |
| D7 | Concurrent listings default 5 |
| D8 | Extend `/marketplace` only — no new slash command |

---

## 6. Phase 0 decision log (`/speckit.plan`)

### D9 — Tax ledger encoding (implicit burn)

- **Decision**: Buyer `apply_club_economy(-gross, source=transfer_buy)`; seller `apply_club_economy(+net, source=transfer_sale)` where `net = floor(gross * 0.9)`. Tax amount recorded in `transfer_sales_log` + `reason_meta` on both ledger rows. No system sink club and no zero-club credit.
- **Rationale**: Matches existing two-party economy patterns; coins simply never reappear (true sink). Avoids inventing a treasury Discord ID.
- **Alternatives considered**: Third ledger row to a `SYSTEM` club — unnecessary identity; duplicate tax as seller debit of −tax after +gross — more moving parts for same net.

### D10 — Card movement = ownership transfer

- **Decision**: On purchase, `UPDATE player_cards SET owner_id = buyer` (clear squad assignment if any — should already be clear). Do **not** delete/reinsert.
- **Rationale**: Preserves XP, level, fatigue, injury, DOB, evolution history, mentor state. Agent sale may still DELETE (NPC liquidation destroys card identity by design).
- **Alternatives considered**: Delete + clone like scouting regen — loses progression; rejected.

### D11 — Price floor / ceiling multipliers

- **Decision**: `floor = max(50, floor(fair * 0.75))`, `ceil = max(floor, floor(fair * 2.5))` where `fair = compute_agent_offer` / `generate_agent_offer`. Config keys `transfer_price_floor_mult` / `transfer_price_ceil_mult` as numerics default `0.75` / `2.5`.
- **Rationale**: OSM-style bounds stop 1-coin alt dumps and absurd gouge without killing market discovery.
- **Alternatives considered**: Unbounded prices — fails FR-013; fixed absolute min/max — unfair across OVR bands.

### D12 — TTL and re-list cooldown

- **Decision**: Listing TTL **72 hours** (`transfer_listing_ttl_hours`). Relist cooldown **6 hours** after P2P purchase for that buyer+card (`transfer_relist_cooldown_hours`), enforced via `transfer_sales_log`.
- **Rationale**: Stale listings return cards; cooldown blunts immediate alt flip without hard identity linking.
- **Alternatives considered**: No expiry — inventory stuck risk; 24h TTL — too aggressive for Discord sparse play; 48h cooldown — heavier than needed for v1.

### D13 — Senior roster capacity on buy

- **Decision**: Purchase rejects if buyer’s non-academy, non-retired card count ≥ `senior_roster_cap` (default 48 from migration 060). Seller’s listed card still counts toward seller until sale completes.
- **Rationale**: Spec edge case; reuses existing config; prevents overflow after youth-academy promote rules.
- **Alternatives considered**: Unlimited buy — fights roster-cap design already shipping.

### D14 — Listed-card exclusion mechanism

- **Decision**: Active listing = `transfer_listings.status = 'active'` with partial unique index on `card_id`. No new `player_cards` boolean. All mutation RPCs (`process_agent_sale`, squad assign, drills, fusion, evo start, list) `EXISTS`/`FOR UPDATE` check. Cog filters join or prefetch listed ids.
- **Rationale**: Single source of truth; avoids denormalized flag drift.
- **Alternatives considered**: `is_transfer_listed` column — easier filters but dual-write risk.

### D15 — Daily soft caps beyond slots

- **Decision**: **Out of v1.** Slot cap 5 + tax + cooldown only.
- **Rationale**: YAGNI until abuse metrics warrant it.

### D16 — Discord filter UX

- **Decision**: Transfer Board uses select menus for position + preset OVR/age/POT bands (not free-text ranges) to fit Discord component limits; detail confirm shows full stats. Optional modal only for **price** on list.
- **Rationale**: Discord select ≤25 options; modals poor for multi-filter; bands cover FR-005 intent.

---

## Sources (competitive)

- [FC 26 Transfer Market – FIFPlay](https://www.fifplay.com/fc-26-transfer-market/)
- [EA FC 26 Tax Calculator – FUTwiz](https://www.futwiz.com/tax-calculator)
- [FC 26 Tax – FIFAUTEAM](https://fifauteam.com/fc-26-tax-calculator/)
- [Top Eleven Auctions](https://www.topeleven.com/auctions-and-bidding/)
- [Top Eleven Help – auction bidding](https://nordeus.helpshift.com/hc/en/3-top-eleven-be-a-soccer-manager/faq/650-how-auction-works-and-what-s-the-best-time-for-a-bid/)
- [OSM Helper Guideline](https://osmhelper.com/guideline/)
- [OSMGuide Tips](https://www.osmguide.com/tips/)
- [FM Online-style Transfer Market help](https://www.footballmanager-online.co.uk/help/transfer.html)

Note: `parallel-cli` was unavailable in this environment; competitive excerpts used general web search. Re-run with `/parallel-setup` if deeper primary-source harvest is needed.
