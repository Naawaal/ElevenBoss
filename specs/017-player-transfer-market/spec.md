# Feature Specification: Player-to-Player Transfer Market

**Feature Branch**: `017-player-transfer-market`

**Created**: 2026-07-14

**Status**: Locked

**Input**: User description: "Pre-integration assessment and design for a player-driven Transfer Market overhaul on `/marketplace`: global buy-it-now listings with custom coin prices, search/filter by position/OVR/age/potential, 10% transfer tax as a coin sink, integration with club finance and inventory, feature-flagged rollout that preserves existing agent sales and scouting, Discord-simple UX with no bidding."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - List a player for sale (Priority: P1)

A manager owns a duplicate or surplus roster player and wants to sell them to another human club for a price they choose, instead of (or before) accepting a fixed agent offer.

**Why this priority**: Without listing, there is no player-driven market. This is the supply side of retention and coin recirculation.

**Independent Test**: A registered club can list an eligible card at a custom coin price, see it under My Listings, and cancel the listing to restore the card to their roster — without any buyer involved.

**Acceptance Scenarios**:

1. **Given** a manager opens `/marketplace` with the P2P market enabled, **When** they choose My Listings → List Player and select an eligible roster card and a coin price, **Then** the card leaves their free roster (cannot be used in XI, drills, fusion, evolution, academy exclude already apply) and appears as an active global listing.
2. **Given** a manager has an active listing, **When** they open My Listings and cancel it, **Then** the card returns to their roster and is no longer purchasable by others.
3. **Given** a card is in the starting XI, active training, active evolution, injured/hospitalized, retired, in academy, or the club is match-locked, **When** the manager tries to list it, **Then** the action is rejected with a clear reason and no listing is created.
4. **Given** a manager already has the maximum number of active listings, **When** they try to list another card, **Then** they are blocked until a listing sells or is cancelled.

---

### User Story 2 - Browse, filter, and buy a listed player (Priority: P1)

A manager wants to find a bargain or a positional upgrade by browsing other clubs’ listings and buying instantly at the posted price.

**Why this priority**: Demand-side discovery is what makes daily engagement and “transfer market” feel real; buy-it-now keeps Discord UX viable.

**Independent Test**: With at least one listing from another club in the market, a buyer can filter, open a listing detail, confirm purchase, and receive the card while paying coins (including tax settled system-side).

**Acceptance Scenarios**:

1. **Given** active listings exist from other clubs, **When** the manager opens Search Market → Transfer Board (players for sale), **Then** they see listings they can filter by position and preset bands for OVR, age, and potential (e.g. OVR 75–79, Age 21–25).
2. **Given** a listing within their coin balance, **When** they confirm Buy Now, **Then** ownership transfers to them, they pay the listed price, the seller receives 90% of that price, and 10% is permanently removed from the economy as transfer tax.
3. **Given** two managers attempt to buy the same listing at once, **When** the first purchase succeeds, **Then** the second receives a clear “already sold / listing unavailable” outcome and no coins are deducted from the loser.
4. **Given** the buyer lacks enough coins, **When** they attempt Buy Now, **Then** purchase fails with an insufficient-funds message and the listing remains.
5. **Given** filters that match no listings, **When** the manager applies them, **Then** they see an empty-state message, not an error.

---

### User Story 3 - Manage my listings and understand tax (Priority: P2)

A manager wants a clear home for their active sale posts, knowing what they will net after tax before someone buys.

**Why this priority**: Trust and clarity drive repeat use; tax visibility prevents “I was shorted” support.

**Independent Test**: From My Listings alone, a seller can see price, estimated net after 10% tax, and cancel — without browsing the global board.

**Acceptance Scenarios**:

1. **Given** one or more active listings, **When** the manager opens My Listings, **Then** each row shows player identity (name, position, OVR, age, POT), listed price, and net proceeds after 10% tax.
2. **Given** a sale completes while they are offline, **When** they next open the market or receive a sale confirmation, **Then** they can tell the card left and coins (net of tax) were credited.

---

### User Story 4 - Keep existing agent sales and scouting while P2P rolls out (Priority: P2)

A manager who still wants instant liquidation or regen signings must not lose those paths when P2P goes live; operators can enable P2P gradually.

**Why this priority**: Safe rollout and economy continuity; US-11 hub already promises Sell + Search + Listings.

**Independent Test**: With the P2P feature flag off, hub behavior matches today (agent sell + scouting; My Listings disabled or hidden). With flag on, all three rails coexist without forcing a migrate.

**Acceptance Scenarios**:

1. **Given** P2P market is disabled, **When** a manager runs `/marketplace`, **Then** Sell Player (agent) and Search Market (scouting) still work; player-to-player list/buy is not offered as live.
2. **Given** P2P market is enabled, **When** a manager opens the hub, **Then** they can still agent-sell, browse scouting, and use Transfer Board list/buy — without replacing either existing rail.
3. **Given** a club hits the daily agent-sale cap, **When** they try another agent sale, **Then** they are blocked as today, but may still list to the P2P market (subject to listing slot caps).

---

### User Story 5 - Daily habit: flip duplicates and hunt bargains (Priority: P3)

Managers return to the market because duplicates from packs/academy and underpriced listings create a reason to check daily.

**Why this priority**: Retention outcome of the feature; not required for MVP correctness but defines success.

**Independent Test**: In a playtest week, managers with surplus cards and managers hunting upgrades both report at least one intentional market visit day that was not match-day driven.

**Acceptance Scenarios**:

1. **Given** a manager receives a duplicate or lower-priority card, **When** they list it same day, **Then** the flow from hub to listed completes in a short, guided interaction (no auctions, no multi-step bidding).
2. **Given** filtered search for a gap (e.g. MID + OVR 70–74 band + Age ≤25 band), **When** results include underpriced listings relative to agent value guidance, **Then** the manager can buy in one confirm step.

---

### Edge Cases

- Buyer and seller are the same Discord account: purchase of own listing is rejected.
- Seller cancels while buyer is mid-confirm: buyer sees listing unavailable; no partial transfer.
- Listing expires (if expiry enabled): card returns to seller roster automatically; no coin movement.
- Buyer’s roster is at capacity: purchase rejects with clear capacity message; listing remains.
- Card on listing is somehow still in XI (data race): purchase/list mutations refuse inconsistent state.
- Sale during season/matchday lock for seller or buyer: blocked consistently with other economy actions.
- Price below minimum or above maximum allowed bound: listing rejected with suggested range.
- Alt-pair attempts to transfer value via 1-coin listings: floor pricing and/or hold rules prevent trivial coin pass (see Assumptions / anti-exploit).
- Scouting pool vs Transfer Board confusion: UI labels clearly separate “Regen Scouting” and “Player Transfers.”

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a manager to create a global buy-it-now listing for an owned eligible player card at a custom coin price within allowed bounds.
- **FR-002**: System MUST enforce listing eligibility: not in starting XI, not in active training, not in active evolution, not injured/hospitalized, not retired, not in academy, not already listed, and club not match-locked.
- **FR-003**: System MUST cap concurrent active listings per club (default 5, configurable).
- **FR-004**: System MUST allow the seller to cancel an unsold listing, restoring the card to their roster.
- **FR-005**: Market search MUST support filtering by Position and preset bands for OVR, Age, and Potential (e.g., OVR 75–79, Age 21–25). Continuous free-range min/max inputs are deferred to avoid Discord Modal complexity.
- **FR-006**: System MUST complete purchases as atomic buy-it-now transfers: one buyer pays listed price; card ownership moves to buyer; listing closes.
- **FR-007**: On a successful P2P sale, system MUST credit the seller **90%** of the listed price and permanently remove **10%** as transfer tax (coin sink). Tax MUST be visible to the seller before list and on My Listings.
- **FR-008**: System MUST prevent a manager from purchasing their own listing.
- **FR-009**: Coin movements for P2P (buyer debit, seller credit, tax sink accounting) MUST use the same club finance ledger patterns as other economy actions — no silent balance edits outside finance rules.
- **FR-010**: Agent sales (`Sell Player` → agent offer) MUST remain available as instant liquidation with existing daily caps and server-side pricing.
- **FR-011**: Scouting pool (regen signings) MUST remain available under Search Market as a distinct rail from player-to-player listings.
- **FR-012**: P2P list/buy MUST be feature-flaggable so operators can keep the current marketplace live without P2P until rollout.
- **FR-013**: Listing price MUST be bounded (floor and ceiling relative to a fair-value guide based on the existing agent-valuation spirit) to reduce alt-account dumping and price manipulation.
- **FR-014**: Hub copy MUST show accurate active listing count (e.g. `n / max`) instead of a hard-coded placeholder.
- **FR-015**: Discord UX MUST remain buy-it-now only — no bidding, auctions, or multi-round timers.
- **FR-016**: Failed purchases or race losses MUST leave buyer coins and seller inventory unchanged and communicate a clear ephemeral outcome.
- **FR-017**: Listed cards MUST be excluded from match play, development actions, and agent sale until cancelled or sold.
- **FR-018**: System SHOULD apply a minimum ownership / time-on-club rule before a newly acquired card (especially one just bought on the market) can be re-listed, to blunt immediate flip exploits between alts.

### Key Entities

- **Transfer Listing**: A buy-it-now offer of one player card by a selling club at a fixed coin price, with status (active / sold / cancelled / expired), timestamps, and tax preview metadata.
- **Listed Player Card**: The same club inventory card, temporarily unavailable for squad/dev while actively listed.
- **Transfer Sale**: A completed P2P transaction: buyer, seller, gross price, tax amount, net seller credit, card identity snapshot for history.
- **Agent Sale (existing)**: Instant NPC buyout at server-computed value; parallel faucet/sink path.
- **Scouting Listing (existing)**: System-owned regen prospects; not player-owned inventory.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a pilot guild cohort, ≥40% of active managers complete at least one successful P2P list or buy within 14 days of enablement.
- **SC-002**: Managers can go from hub → listed sale (or hub → filtered buy confirm) in under 2 minutes of focused interaction.
- **SC-003**: After launch, ≥95% of completed P2P sales correctly show seller net = 90% of listed price (tax sink observed in economy reporting).
- **SC-004**: With feature flag off, existing agent-sale and scouting flows retain pre-change success behavior (no regression in smoke checks).
- **SC-005**: Concurrent buy races produce at most one successful transfer per listing; zero duplicated cards and zero double-debits in audit of race tests.
- **SC-006**: Support/ops do not see a surge of “coins vanished / card stuck” tickets attributable to P2P in the first 30 days when tax/eligibility messages are clear (qualitative: ≤ baseline + noise for unrelated economy tickets).
- **SC-007**: Playtest managers rate market UX as “simple enough for Discord” (majority agree no bidding needed) in a short post-pilot pulse.

## Assumptions

- Agent sales remain a lower-friction / often lower-proceeds exit alongside P2P; they are not removed in v1.
- Default concurrent listing slots = 5 (already signaled in hub UI copy).
- Transfer tax = 10% of listed price, deducted from seller proceeds (buyer pays listed price in full).
- Price bounds use the existing agent-offer valuation as a fair-value guide: floor **0.75×** / ceiling **2.5×** (plan D4 / D11).
- Market is **global across Discord guilds** (clubs are keyed by Discord user identity already); not per-server silent markets.
- Roster capacity rules from other features (e.g. senior roster cap) apply to buyers at purchase time.
- No auctions / snipe timers in v1 (informed by Discord interaction model and Top Eleven auction complexity).
- Feature flag defaults off until migration + verification complete.
- Soft anti-alt measures in v1: price floors/ceilings + re-list cooldown; hard multi-account identity linking is out of scope.
- Expiry of stale listings (auto-return) is **72 hours** (plan D5 / D12).

## Out of Scope

- Auction / bid / Buy-Now-and-Start-Price dual models
- Cash + tokens hybrid P2P checkout
- Direct manager-to-manager private offers outside the public board
- Cross-item trades (player-for-player swaps without coins)
- New slash commands beyond extending `/marketplace`
- Removing or rebalancing agent sale formula beyond coexistence with P2P
- Real-money marketplace or RMT tooling
