# Feature Specification: Marketplace Intelligence & Market Analytics

**Feature Branch**: `043-marketplace-intelligence`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Marketplace V2 — Economy Intelligence & Market Analytics: extend the existing `/marketplace` so it is observable, measurable, and data-driven. Add durable transfer history, ownership career history, real-data price discovery, internal market analytics for balancing, improved Transfer Board sorting, and long-term data collection — without new flashy market mechanics, parallel systems, or new slash commands."

**Parent / related**: Extends Locked `specs/017-player-transfer-market` (P2P board, tax, listings, sales log). Coexists with agent sales, regen scouting, and youth academy scouting. Integrity constraints from US-42 / marketplace integrity remain in force.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Durable completed-transfer history (Priority: P1)

After a player-to-player sale completes, the game permanently records who sold, who bought, what was paid, tax, fair value at sale, and a snapshot of the player’s market-relevant attributes at that moment. Managers and operators can later answer “what actually sold?” without relying on memory or live card state.

**Why this priority**: Every analytics, price-discovery, and ownership feature depends on immutable sale facts. The market already writes a basic sale audit on purchase; this story makes that history complete and reusable.

**Independent Test**: Complete one P2P buy; verify a permanent history record exists with seller, buyer, price, tax, fair value, timestamp, and card attribute snapshot; verify a second transfer of the same card appends another record without altering the first.

**Acceptance Scenarios**:

1. **Given** a successful P2P purchase, **When** the sale settles, **Then** an append-only transfer history record is stored with player identity, seller club, buyer club, gross price, tax, seller net, fair value at sale, timestamp, and snapshot fields for rarity, position, overall, potential, and age at sale.
2. **Given** an existing transfer history record, **When** the card later changes owner, overall, or rarity, **Then** the historical record’s snapshot and money fields remain unchanged.
3. **Given** a completed sale, **When** an operator queries history by card, buyer, seller, or time range, **Then** results return efficiently without scanning unrelated market tables.
4. **Given** a purchase that fails (insufficient coins, race loss, own listing), **When** the failure is returned, **Then** no transfer history record is created.

---

### User Story 2 - Player ownership career trail (Priority: P1)

Every player card keeps a career trail of clubs that have owned it. After each completed P2P transfer, a new ownership segment is appended. Managers can open a card they own (or a listing they are considering) and see the club chain over time.

**Why this priority**: Ownership trail is the manager-facing proof that the market has memory; it also underpins future career timelines without inventing a second history system later.

**Independent Test**: Buy a listed card that previously sold at least once; view ownership history and see prior club(s) plus the new current club, with earlier segments unchanged.

**Acceptance Scenarios**:

1. **Given** a card is first acquired by a club (pack, academy/regen sign, or other existing acquisition path covered by this feature’s wiring), **When** ownership begins, **Then** an ownership history segment records that club as owner starting at that time.
2. **Given** a completed P2P transfer, **When** ownership moves, **Then** the previous ownership segment closes and a new segment opens for the buyer; earlier segments remain readable.
3. **Given** a manager views an owned card’s career (or a Transfer Board listing detail), **When** ownership history is available, **Then** they see an ordered club trail (oldest → newest / current) with enough identity to recognize clubs (club name at minimum).
4. **Given** a card is later sold again or leaves the market path, **When** history is viewed, **Then** past ownership segments still appear (history survives subsequent transfers).
5. **Given** insufficient history (brand-new card with only current owner), **When** the manager opens career history, **Then** they see a clear empty/minimal state (current club only), not invented prior clubs.

---

### User Story 3 - Price discovery from real market data (Priority: P1)

Before listing or buying, a manager can see price-discovery facts derived only from real marketplace data for a comparable cohort: average and median completed sale prices, lowest and highest active listings, recent completed sales, active listing count, and a simple trend when enough history exists. If data is thin, the UI says so instead of inventing numbers.

**Why this priority**: Highest manager-facing ROI for “intelligence” — reduces blind pricing and bargain hunting guesswork without adding new market mechanics.

**Independent Test**: With ≥ minimum completed sales in a cohort and several active listings, open list or listing-detail price discovery and confirm displayed figures match those real sales/listings; with fewer than the minimum, confirm “insufficient data” rather than fabricated averages.

**Acceptance Scenarios**:

1. **Given** enough completed P2P sales exist for the comparable cohort, **When** a manager opens price discovery while listing a similar card or inspecting a board listing, **Then** they see average sale price, median sale price, recent completed sales summary, and active listing count for that cohort.
2. **Given** active listings exist in the cohort, **When** price discovery is shown, **Then** lowest and highest active listing prices are shown from those real listings.
3. **Given** enough chronological sales exist, **When** trend is shown, **Then** trend reflects recent completed prices vs an earlier window (e.g. up / down / flat) and is labeled as derived from real sales — never a guessed “recommended price.”
4. **Given** fewer than the minimum completed sales for the cohort, **When** the manager opens price discovery, **Then** the surface states that market data is insufficient and omits invented averages/medians/trends.
5. **Given** P2P market is disabled, **When** a manager uses agent sale or regen scouting, **Then** P2P price-discovery panels are not presented as live Transfer Board intelligence.

---

### User Story 4 - Improved Transfer Board sorting (Priority: P2)

Managers browsing the Transfer Board can sort filtered results by useful orders (lowest price, highest price, highest overall, highest potential, newest, ending soon, best value) while keeping the existing filter bands and Discord-scale result limits.

**Why this priority**: Cheap UX win on the existing search surface; improves bargain hunting without new queries per sort if the board already loads a bounded set.

**Independent Test**: With mixed listings loaded, apply each sort option and confirm order matches the chosen criterion; filters still apply; empty filter+sort combinations show the existing empty state.

**Acceptance Scenarios**:

1. **Given** active Transfer Board listings after filters, **When** the manager chooses a sort (Lowest Price, Highest Price, Highest OVR, Highest Potential, Newest, Ending Soon, Best Value), **Then** the visible result order matches that sort.
2. **Given** filters that already narrow the board, **When** sort changes, **Then** filters remain applied and no duplicate board fetch is required beyond the existing board load pattern.
3. **Given** Best Value sort, **When** results are ordered, **Then** value is defined consistently as listed price relative to fair value at browse time (lower ratio = better value), and listings without a fair-value guide sort last or are excluded with clear behavior.
4. **Given** no listings match, **When** any sort is selected, **Then** the manager sees the empty-state message, not an error.

---

### User Story 5 - Internal market analytics for balancing (Priority: P2)

Operators can answer balancing questions from durable market facts: marketplace volume, agent vs manager sales, expired listings, average time-to-sale, coins moved, coins removed by tax, daily transaction volume, listing success rate, top traded positions/rarities, highest transfers, and most active clubs — without building a flashy player-facing dashboard.

**Why this priority**: Makes the market measurable for future economy tuning; data collection is the product, not a Discord admin theme park.

**Independent Test**: After a known set of list/buy/cancel/expire/agent-sale events in a test window, an operator can produce the metric set for that window from stored market/economy facts and reconcile totals with those events.

**Acceptance Scenarios**:

1. **Given** completed P2P sales, agent sales, and listing terminal states in a date range, **When** an operator runs the analytics view for that range, **Then** they can obtain: P2P volume (count + gross coins), tax coins removed, agent-sale count + coins paid, expired listing count, average duration for sold listings, listing success rate (sold ÷ created in window), and daily transaction volume.
2. **Given** enough sales with attribute snapshots, **When** the operator requests breakdowns, **Then** top traded positions, top traded rarities, highest transfers, and most active clubs (by sale count or volume) are available from real records.
3. **Given** analytics are requested, **When** a metric has no supporting rows, **Then** the result is zero / empty — not estimated filler.
4. **Given** managers use `/marketplace` normally, **When** analytics are computed, **Then** managers are not required to open an analytics screen for the market to function (analytics are internal/ops-facing in this feature).

---

### User Story 6 - Long-term data collection with low overhead (Priority: P3)

The marketplace continuously accumulates facts needed for future balancing (daily sales, listing lifetime, agent vs player mix, unsold rate, pricing distribution, rarity/position demand, economy inflow/outflow tied to market sources) as a byproduct of normal list/buy/expire/agent flows — not as a heavy parallel telemetry product.

**Why this priority**: Future dynamic demand, weekly reports, and featured listings need today’s append-only facts; collection must not slow the hub.

**Independent Test**: Run a scripted day of market actions; confirm daily aggregates or equivalent queryable facts exist afterward; confirm hub list/buy latency does not regress beyond agreed budget in Success Criteria.

**Acceptance Scenarios**:

1. **Given** normal market activity across a UTC day, **When** the day closes (or on next analytics read), **Then** operators can obtain daily sales count, average listing lifetime for sold/expired listings, agent vs P2P sale mix, and unsold/expired share without manual log scraping.
2. **Given** a manager lists, buys, cancels, or agent-sells, **When** the action completes, **Then** any extra recording required for intelligence does not introduce a second coin pipe or a second ownership mutation path.
3. **Given** high listing browse traffic, **When** managers open Transfer Board / price discovery, **Then** reads use pre-aggregated or indexed history rather than full-table scans of all historical sales on every open.

---

### Edge Cases

- **Thin market / cold start**: Price discovery and trend show insufficient-data states until the cohort minimum is met; analytics return zeros.
- **Card deleted by agent sale**: Ownership history for that card remains queryable as a closed career (no fabricated “current club”); transfer history rows already written remain immutable.
- **Buyer cancels Discord mid-confirm / race loss**: No history or ownership segment is written; listing remains for the winner path only.
- **Stale ephemeral board after a sale**: Next board refresh omits sold listing; price-discovery active high/low updates on next open.
- **Historical sales before this feature**: Pre-enrichment sale rows may lack attribute snapshots; price discovery and breakdowns ignore null-snapshot rows or treat them as incomplete rather than inventing attributes.
- **P2P feature flag off**: History/analytics for past sales remain readable to ops; manager Transfer Board / P2P price discovery stay unavailable; agent sale and scouting unchanged.
- **Club rename / deleted club identity**: Ownership trail shows the best available club label recorded at segment time; if a club row is gone, show a stable fallback label rather than breaking the trail.
- **Self-buy / payroll block / roster cap failures**: No transfer or ownership history side effects.
- **Best Value with missing fair value**: Deterministic fallback (sort last); no crash.
- **Double-tap Buy Now**: At most one sale record and one ownership transition (existing purchase atomicity).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On every successful P2P purchase, the system MUST append an immutable transfer history record containing seller, buyer, card identity, gross price, tax amount, seller net, fair value at sale, timestamp, and attribute snapshot (rarity, position, overall, potential, age).
- **FR-002**: Transfer history records MUST be append-only (no update/delete of money or snapshot fields after write) and MUST remain after later transfers of the same card.
- **FR-003**: Transfer history MUST be queryable by card, buyer, seller, and time range with indexed access suitable for analytics and cooldown/history reuse.
- **FR-004**: The system MUST maintain an ownership career trail per card: append a new ownership segment on covered acquisition and on each successful P2P transfer; prior segments MUST remain readable.
- **FR-005**: Managers MUST be able to view ownership career history for cards they own and for cards shown on Transfer Board listing detail (ordered club trail).
- **FR-006**: Price discovery MUST expose, when data exists: average completed sale price, median completed sale price, lowest active listing, highest active listing, recent completed sales, active listing count, and a simple trend from real completed sales.
- **FR-007**: Price discovery MUST NOT invent values. When the comparable cohort has fewer than the configured minimum completed sales, the UI MUST show an insufficient-data state instead of averages/medians/trends.
- **FR-008**: Comparable cohort for price discovery MUST be defined consistently (same position and rarity, overall within ±3 of the subject card, completed P2P sales only) and documented to managers as “similar players.”
- **FR-009**: Transfer Board MUST offer sorts: Lowest Price, Highest Price, Highest OVR, Highest Potential, Newest, Ending Soon, Best Value — applied to the already-filtered result set without replacing existing position/OVR/age/POT band filters.
- **FR-010**: Best Value MUST order by listed price ÷ fair value (ascending), with missing fair value handled deterministically.
- **FR-011**: Operators MUST be able to obtain internal analytics for a date range: P2P volume, agent sales volume, expired listings, average sale duration, coins transferred, tax coins removed, daily transaction volume, listing success rate, top traded positions, top traded rarities, highest transfers, most active clubs.
- **FR-012**: Analytics and price discovery MUST reuse existing marketplace sale/listing/economy facts where they already exist; the feature MUST NOT create a parallel coin ledger or a second purchase path.
- **FR-013**: Long-term collection MUST capture daily market activity facts (sales, listing lifetimes, agent vs P2P mix, unsold/expired share, pricing and rarity/position distributions, market-related coin inflow/outflow) with minimal added work on the hot path.
- **FR-014**: All coin movements remain on the existing club economy ledger rules; market intelligence MUST NOT debit/credit coins itself.
- **FR-015**: Agent sales, regen scouting, and youth academy scouting MUST continue to work; this feature MUST NOT remove or replace those rails.
- **FR-016**: No new slash command is introduced; all manager-facing surfaces extend `/marketplace` (and existing card/listing detail entry points already used there).
- **FR-017**: Failed or rolled-back purchases MUST leave transfer history and ownership trail unchanged.
- **FR-018**: Listing create/cancel/expire behavior from the existing transfer market MUST remain; intelligence layers observe those outcomes (e.g. expired counts) without changing eligibility, tax rate, or price bounds.
- **FR-019**: Performance: Transfer Board open and price-discovery open MUST remain usable on Discord ephemeral flows (no multi-minute waits); history writes on purchase MUST occur in the same successful sale outcome managers already trust (no “sold but history missing” under normal operation).
- **FR-020**: Future features (dynamic demand, weekly reports, featured listings, seasonal events) MUST be supportable from the same history/ownership/aggregate facts without requiring a redesign of sale recording — those features are not delivered in this spec.

### Key Entities

- **Transfer History Record**: Immutable completed P2P sale fact (parties, money, tax, fair value, time, card attribute snapshot).
- **Ownership Segment**: Time-bounded record that a club owned a card; closes when ownership leaves that club; chain forms the career trail.
- **Price Discovery Summary**: Read model over real completed sales and active listings for a comparable cohort (averages, medians, highs/lows, count, trend, or insufficient-data).
- **Market Analytics Snapshot**: Operator-facing metrics for a time window derived from listings, transfer history, agent-sale economy facts, and expiry outcomes.
- **Transfer Listing (existing)**: Active/sold/cancelled/expired buy-it-now offer; remains the live board source.
- **Agent Sale / Scouting Rails (existing)**: Parallel market exits/entries; contribute to analytics mix but are not P2P listings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of successful P2P purchases in verification produce exactly one new transfer history record and exactly one ownership transition (prior segment closed + buyer segment opened) with no money/snapshot mutation of older records.
- **SC-002**: Managers can open ownership career history for an owned or listed card and identify the club trail in under 10 seconds of reading.
- **SC-003**: When a cohort has at least the minimum completed sales, price discovery shows average and median that match recomputation from those sales within rounding tolerance; when below minimum, 100% of opens show insufficient-data (0 fabricated figures in test matrix).
- **SC-004**: Managers can change Transfer Board sort among the seven modes and see a correctly reordered list without losing active filters, in the same browse session.
- **SC-005**: For a seeded test day with known list/buy/expire/agent events, operators can recover volume, tax removed, success rate, and agent vs P2P mix that reconcile to the seed (±0 for counts; money totals exact).
- **SC-006**: Marketplace hub and Transfer Board browse remain within existing hot-path expectations for ephemeral Discord use — no perceived multi-step “loading forever” regression versus pre-feature board open in smoke checks.
- **SC-007**: Zero regressions in purchase atomicity, tax split, agent-sale caps, and scouting purchase success versus pre-feature behavior in smoke/race checks.
- **SC-008**: After feature delivery, a balancing question such as “how much tax did the market remove last 7 days?” is answerable from stored facts without reading application logs.

## Assumptions

- Extends the existing P2P market (`017`); does not redesign tax (default 10%), price bounds, listing TTL, slot cap, or buy-it-now model.
- Existing completed-sale audit is the foundation for transfer history and is enriched (attribute snapshot + fair value) rather than replaced by a disconnected parallel log.
- Ownership history is new; current `owner_id` alone is insufficient and is not rewritten into fake past clubs for cards that never recorded segments.
- Forward-only enrichment: sales completed before snapshot fields existed may have null snapshots; analytics skip or partially count them rather than backfilling guessed attributes from today’s card.
- Comparable cohort default: same position + same rarity + overall within ±3; minimum completed sales for averages/median/trend = **5**.
- Trend default: compare median of last 7 days of cohort sales vs prior 7 days → up / down / flat (or hide trend if either window lacks data).
- Best Value = lower `listed_price / fair_value` is better; fair value uses the same guide spirit as listing bounds (agent-valuation guide).
- Internal analytics in this feature are **ops-facing** (queryable metrics / operator tooling), not a player Discord “Market HQ” dashboard. Player-facing surfaces are transfer/ownership history views and price discovery.
- Agent sales destroy cards today; ownership trail closes without a buyer club; agent volume still counts in analytics via existing economy sale facts.
- Regen/youth scouting acquisitions may open an ownership segment when wiring is practical; pack openings are included only if an existing acquisition hook can append without a new slash command — otherwise deferred with explicit plan note (P2P + explicit market acquisitions are mandatory).
- No new slash commands; `/marketplace` remains the hub.
- US-42 marketplace integrity (atomic purchase, no self-buy, ledger sources) remains mandatory.
- Global market across guilds (club = Discord user identity), same as `017`.

## Out of Scope

- Dynamic market demand formulas, weekly auto-posted market reports, featured listings, seasonal market events
- Auctions, bidding, private offers, player-for-player trades
- Changing transfer tax rate, fair-value formula, listing TTL, or agent-offer formula (except reading fair value into history/discovery)
- Player-facing full analytics dashboard / admin Discord cog for every metric
- Real-money or RMT tooling
- Rebuilding marketplace as a separate service/subsystem
- New slash commands or new hub buttons unrelated to history, discovery, sort, or ops analytics access
- Invented “recommended list price” that is not labeled as derived from real comparable sales (and only when data suffices)

## Dependencies

- Locked transfer market behavior and sale audit from `specs/017-player-transfer-market`
- Existing club economy ledger and agent-sale daily accounting
- Existing Transfer Board filters and Discord select result limits
- Marketplace integrity / economy source-sink registry expectations (tax observability)
- Hub hot-path discipline for `/marketplace` (gather/timer patterns already in place)

## Risks & Compatibility Notes

- Enriching sale recording must stay inside the successful purchase outcome so history cannot diverge from coins/ownership.
- Ownership trail for agent-deleted cards must not cascade-delete history.
- Thin markets will dominate early life after enablement — insufficient-data UX is required to protect trust.
- Board currently loads a bounded listing set then filters in-app; sorts should respect that bound and not silently promise a global ordered market of unlimited size.
- Payroll strike blocks, match locks, and roster caps remain authoritative; intelligence features must not bypass them.
)
