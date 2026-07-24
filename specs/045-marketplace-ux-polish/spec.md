# Feature Specification: Marketplace V1.5 — Professional UX & Polish

**Feature Branch**: `045-marketplace-ux-polish`

**Created**: 2026-07-24

**Status**: Implemented — Discord smoke recommended after bot restart

**Input**: User description: "ElevenBoss Marketplace V1.5 — Professional UX & Polish: transform the existing `/marketplace` into a polished, AAA-quality experience comparable to modern football management games. Backend V1 is feature-complete (agent sales, P2P board, scouting, history, ownership, discovery, analytics, sorts, filters, atomic buys, anti-exploit). Do NOT build new marketplace mechanics. Analyze first; reuse existing architecture; prioritize usability, clarity, and consistency."

**Parent / related**: Extends Implemented `specs/017-player-transfer-market` and `specs/043-marketplace-intelligence`. Does **not** reopen match V3 (`044`), wages, or academy youth scout as marketplace scope. Integrity (US-42.6 marketplace) remains in force.

**Companion audit**: Full workspace UX audit, journeys, consistency, IA, performance, and prioritized opportunities live in [research.md](./research.md) (Phases 1–10 of the master prompt).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Faster browse → buy with scannable board (Priority: P1)

A manager opens the Transfer Board, sees a clear preview of listings (name, overall, price, time remaining, and enough hints to compare), filters/sorts without confusion, inspects a player, and completes purchase with fewer unnecessary steps and without losing market context on the final confirm.

**Why this priority**: Browse→buy is the daily market climax; current path is ~8–12 interactions with an opaque results list — highest retention/usability ROI without new mechanics.

**Independent Test**: With P2P on and ≥3 active listings, open Transfer Board → apply default filters → see a scannable preview → select → buy confirm still shows key value context → purchase succeeds once.

**Acceptance Scenarios**:

1. **Given** active Transfer Board listings after filters, **When** results are shown, **Then** the manager sees a compact scannable preview (at least name, overall, ask price, and time remaining or ending-soon cue) before or beside selecting a player — not only “N listing(s). Select…”.
2. **Given** a listing with a known expiry, **When** the manager browses results or opens detail, **Then** time remaining (or clear “ending soon”) is visible.
3. **Given** a listing detail with fair-value context available, **When** the manager views the player, **Then** ask price is shown alongside a fair-value comparison (e.g. ask vs fair) without inventing a “recommended price”.
4. **Given** the manager taps Buy and reaches confirmation, **When** they review the confirm, **Then** essential decision context (price, overall, and market/fair cue already shown on detail) remains available — not stripped to a bare number.
5. **Given** default “Any” filters, **When** the manager wants to browse quickly, **Then** they can reach results with no more interactions than today (and preferably fewer forced steps) without losing filter power for power users.

---

### User Story 2 — Market intelligence visible where decisions happen (Priority: P1)

Managers see existing price-discovery and ownership facts (from Marketplace Intelligence) presented clearly on listing detail and buy/list confirms: readable trend language, recent comparable sales when returned by discovery, and ownership trail where already appropriate — never fabricated stats.

**Why this priority**: 043 already ships the data; managers still miss half of it (unused `recent_sales`, discovery dropped on buy confirm, dense one-liners).

**Independent Test**: Open a listing with sufficient cohort data; confirm discovery shows readable avg/median/active/trend and recent sales summary; open buy confirm and still see a compact market cue; open list confirm and still see discovery.

**Acceptance Scenarios**:

1. **Given** price discovery returns sufficient data including recent sales, **When** listing detail (or list confirm) is shown, **Then** the manager sees a short recent-sales summary derived only from that payload — not invented rows.
2. **Given** trend is `up` / `down` / `flat`, **When** discovery is shown, **Then** wording/icons make the trend obvious to a non-technical manager.
3. **Given** discovery was loaded for a listing, **When** the manager opens Buy confirm, **Then** a compact market/fair cue remains (full wall of text optional to omit).
4. **Given** insufficient cohort data, **When** discovery is shown, **Then** the UI states data is insufficient and does not invent averages or trends.
5. **Given** ownership history exists for a listed card, **When** detail is opened, **Then** the career trail remains available in a readable, compact form (already on detail; polish clarity, do not invent clubs).

---

### User Story 3 — Cohesive Marketplace language and controls (Priority: P2)

Hub, Transfer Board, My Listings, Agent Sale, and Regen Scouting feel like one product: consistent naming, Back labels, button emphasis, and confirm patterns so managers are not learning four synonyms for the same place.

**Why this priority**: Naming soup (“Global Transfer Market” / “Marketplace” / “Search Market” / “Transfer Board”) raises cognitive load before any economy decision.

**Independent Test**: Walk hub → Search → Board → Back → Agent → Scouting; every screen uses one primary product name and consistent Back/confirm vocabulary.

**Acceptance Scenarios**:

1. **Given** the manager opens `/marketplace`, **When** they read the hub, **Then** title and body use one primary name (e.g. Marketplace) with clear sub-areas (Transfer Board, Scouting, Agent, My Listings).
2. **Given** any marketplace child screen, **When** they use navigation, **Then** Back actions use a consistent label pattern.
3. **Given** purchase, list, agent sale, or scout sign confirms, **When** shown, **Then** confirm/cancel affordances follow a consistent style language (destructive vs success) appropriate to irreversibility.
4. **Given** empty, gated, or error states, **When** shown, **Then** copy uses shared ownership/session phrasing where the same failure occurs (no three different “not yours” wordings for the same idea).

---

### User Story 4 — Listing & selling clarity (Priority: P2)

Managers managing listings and selling to the agent see expiry, fair context, and enough card truth (including potential on agent offers) to decide confidently; listing success/failure feedback is clear and rewarding without new mechanics.

**Why this priority**: My Listings already fetches expiry but hides it; agent offers hide POT despite using it in pricing — polish completes existing flows.

**Independent Test**: Open My Listings with an active listing → see time remaining; open agent offer → see POT (and rarity if already available) before confirm; complete list confirm with discovery still readable.

**Acceptance Scenarios**:

1. **Given** the manager has active listings with expiry timestamps, **When** they open My Listings, **Then** each listing shows time remaining (or end time) clearly.
2. **Given** an agent offer screen, **When** shown, **Then** potential (and other already-available card facts used in pricing) are visible before Confirm Sale.
3. **Given** a successful list or sale, **When** the result is shown, **Then** the manager gets a concise success summary (what sold/listed, price, and net where relevant) without a wall of text.
4. **Given** validation failure (bounds, ownership, lock), **When** returned, **Then** the message is specific and actionable.

---

### User Story 5 — Leaner marketplace loads (Priority: P3)

Common marketplace opens (hub, board select/sort, list/sell menus) avoid redundant full-table fetches and unnecessary re-queries so interactions feel snappier on mobile, without changing settlement semantics.

**Why this priority**: Perf polish supports “feels premium”; secondary to visible UX but required for AAA feel under Discord latency.

**Independent Test**: Open Transfer Board, change sort, select a listing — board listing query is not repeated on every select if results are already in memory; training/eligibility queries are scoped to the manager’s cards.

**Acceptance Scenarios**:

1. **Given** Transfer Board results are already loaded, **When** the manager changes sort among the loaded set or selects a listing, **Then** the client does not needlessly re-fetch the full board for that interaction (Apply Filters / post-purchase refresh may still fetch).
2. **Given** Sell to Agent or List Player eligibility checks, **When** those screens open, **Then** training/lock checks are scoped to the manager’s relevant cards — not an unbounded global training scan.
3. **Given** hub open, **When** player row is loaded, **Then** only fields needed for marketplace gating/display are requested (no unnecessary full-row habit where a narrow select suffices).

---

### Edge Cases

- P2P flag off: hub still feels cohesive; Search may jump to scouting — naming and Back labels stay consistent.
- Empty board / thin discovery / no ownership history: graceful empty copy, never fabricated market facts.
- Discord Select 25-cap: behavior remains; copy may explain “showing up to 25” when truncated — no new pagination system required in V1.5.
- Stale followup confirm after listing sold elsewhere: existing race errors remain authoritative; polish may clarify the error.
- Mobile weak connection: defer remains; success/error must still be readable after defer.
- Double-tap Buy/Confirm: settle-once / ownership locks unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Feature MUST polish existing `/marketplace` surfaces only — no new slash commands, hubs, or parallel marketplace systems.
- **FR-002**: Feature MUST NOT invent market numbers; only existing discovery, fair-value, listing, and ownership data may be shown.
- **FR-003**: Transfer Board results MUST present a scannable listing preview including time-remaining (or ending-soon) cues when expiry is known.
- **FR-004**: Listing detail MUST surface rarity (when known) and ask-vs-fair comparison when fair value is available.
- **FR-005**: Buy confirmation MUST retain compact market/fair decision context from the prior detail step.
- **FR-006**: Price discovery presentation MUST include readable trend language and recent sales when the existing discovery payload provides them.
- **FR-007**: My Listings MUST display listing time remaining using already-available expiry data.
- **FR-008**: Agent offer screens MUST show potential (and other already-available pricing-relevant facts) before confirm.
- **FR-009**: Marketplace naming and Back/confirm vocabulary MUST be consistent across hub, board, listings, agent, and scouting.
- **FR-010**: Feature MUST preserve atomic purchase/list/agent/scouting RPCs, tax rules, locks, and anti-exploit validation — polish presentation and path only.
- **FR-011**: Feature MUST NOT call ops-only `get_market_analytics` from player hub opens (043 contract remains).
- **FR-012**: Feature SHOULD reduce redundant board re-fetches and unbounded eligibility queries on hot paths without changing outcomes.
- **FR-013**: Success and validation failure messages MUST be concise, specific, and consistent in tone.
- **FR-014**: Out of scope: new market mechanics, Redis, Ranked, wages flips, merging academy youth scout into Transfer Board, seller sale DMs, true multi-page browse beyond Discord Select limits (unless a later spec).

### Key Entities

- **Marketplace Hub**: Single entry `/marketplace` with coherent sub-areas.
- **Transfer Board Listing Preview**: Compact row/field set for browse decisions.
- **Price Discovery Presentation**: Manager-readable projection of existing discovery payload.
- **Confirm Surface**: Buy / list / agent / scout confirmation with retained decision context.
- **Design Language Tokens**: Shared naming, labels, and confirm affordances (conceptual — not a new DB table).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Happy-path browse→buy (default filters, no sort change) requires fewer than today’s ~8 forced interactions, or the same count with a scannable preview that removes “blind select” (playtest: ≥8/10 managers can name price and time-left of a listing without opening Select first).
- **SC-002**: On a sample of listings with known `expires_at`, 100% of My Listings and board preview/detail surfaces show a time-remaining cue.
- **SC-003**: When discovery returns `recent_sales` and a trend, ≥90% of playtest managers correctly interpret trend direction from the UI alone.
- **SC-004**: Buy confirm retains at least price + overall + one market/fair cue in 100% of V1.5 buy flows that had discovery/fair on detail.
- **SC-005**: Hub and primary child screens use one primary product name; zero conflicting titles on the hub embed.
- **SC-006**: After polish, selecting a board listing does not re-query the full board listing set solely to render detail (verified by code review / instrumentation in soak).
- **SC-007**: No increase in failed purchases attributable to polish; settlement semantics unchanged in a 20-purchase sample.

## Assumptions

- Backend from 017 + 043 is complete enough; this feature is presentation, path, consistency, and light perf — not new RPCs unless a tiny read helper is unavoidable (prefer none).
- P2P may be on or off; polish must not break the flag-off scouting shortcut.
- Discord embed/select limits remain the UI ceiling; “AAA” means clarity within those limits, not a website.
- Ops analytics stay ops-only.
- Favorite filters / recently viewed are optional stretch only if they fit low-effort reuse; not required for MVP stories above.

## Out of Scope

- New marketplace mechanics (auctions, loans, trade offers, featured carousel)
- New slash commands or merging `/store` / academy into marketplace
- Parallel history/analytics systems
- Invented “AI recommended price”
- Full pagination beyond Select(25) as a new product surface
- Public website market UI
- Match engine / wages / Ranked work

## Dependencies

- `specs/017-player-transfer-market` (board, tax, listings)
- `specs/043-marketplace-intelligence` (discovery, ownership, sorts, analytics RPC)
- Existing `marketplace_cog.py` / `marketplace_transfer.py` views
- US-42.6 marketplace integrity invariants

## Risks & Compatibility Notes

- Over-dense embeds can worsen mobile readability — prefer hierarchy and short fields over dumping every 043 field.
- Changing confirm from followup→edit (or vice versa) can surprise mid-session managers — prefer consistent patterns with clear ephemeral ownership.
- Caching board listings in-memory across selects must still refresh after purchase/cancel and honor races via RPC errors.
- Visual polish must not hide tax/net clarity that protects seller trust.
)
