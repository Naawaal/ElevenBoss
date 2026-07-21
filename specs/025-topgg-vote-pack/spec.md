# Feature Specification: Top.gg Vote Gate for Free Store Pack

**Feature Branch**: `025-topgg-vote-pack`

**Created**: 2026-07-21

**Status**: Planned

**Input**: User description: "Add Top.gg voting requirement to the free gacha pack claim flow inside `/store`. No new slash command. Dynamic verification via Top.gg API at claim time (vote within 12h). Handle stale/missing votes, API downtime, and double-claim prevention. Button becomes Vote & Claim with cooldown timer after success."

## Background & Motivation

The Store hub (`/store`) currently grants a **free 5-card pack** every 22 hours with no external action required. Top.gg voting is a standard discovery growth loop for Discord bots. Gating the free pack on a verified Top.gg vote rewards supporters, drives listing visibility, and keeps the reward inside the existing Store button — no new commands or hubs.

**Baseline (today)**: See [research.md](./research.md) — `StoreHubView` → `claim_daily_pack` RPC, `players.last_claim_at`, zero Top.gg code.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Vote Then Claim (Priority: P1)

As a registered manager, I must vote for ElevenBoss on Top.gg before I can claim my free pack, using the same Store button I use today.

**Why this priority**: Core product change — without vote verification, the feature does not exist.

**Independent Test**: Manager with no recent vote clicks the Store pack button → sees vote link → votes on Top.gg → returns and clicks again → receives 5-card pack embed.

**Acceptance Scenarios**:

1. **Given** I am registered, pack cooldown has elapsed, and I have **not** voted on Top.gg within the last 12 hours, **When** I click **Vote & Claim Free Pack** in `/store`, **Then** I receive an ephemeral embed with the Top.gg vote URL and instructions to vote, then click the button again — **no pack is granted**.
2. **Given** I voted on Top.gg within the last 12 hours (including via the website, not only in-Discord), **When** I click **Vote & Claim Free Pack**, **Then** the bot verifies my vote via Top.gg API and grants the standard 5-card free pack.
3. **Given** I successfully claimed a pack, **When** I open `/store` again, **Then** the pack button is disabled with a cooldown timer until the next claim window.
4. **Given** I voted more than 12 hours ago and have not voted again, **When** I try to claim, **Then** I am prompted to vote again (same as scenario 1).

---

### User Story 2 - Double-Claim & Vote Replay Prevention (Priority: P1)

As the platform, we must not grant two packs for one vote cycle or bypass cooldown via rapid clicks.

**Why this priority**: Economy integrity — a free pack is a meaningful faucet.

**Independent Test**: After one successful claim, second click within cooldown is rejected; same vote timestamp cannot fuel two claims even if Top.gg still reports `voted=1`.

**Acceptance Scenarios**:

1. **Given** I claimed a pack successfully, **When** I click the button again before cooldown ends, **Then** I see the cooldown embed and receive **no** cards (existing RPC `COOLDOWN:` behavior preserved or aligned to new window).
2. **Given** I claimed using vote cycle *V*, **When** I attempt another claim while Top.gg still shows an active vote from *V* but cooldown has somehow elapsed, **Then** the server rejects the claim unless a **new** vote cycle exists (server tracks consumed vote identity/timestamp).
3. **Given** two simultaneous claim clicks, **When** both reach the server, **Then** at most one pack is granted (RPC `FOR UPDATE` + atomic vote consumption).

---

### User Story 3 - API Failure Graceful Degradation (Priority: P2)

As a manager, I get a clear message when Top.gg is unreachable — not a raw error or silent failure.

**Why this priority**: External dependency reliability; avoids support confusion during outages.

**Independent Test**: Simulate Top.gg timeout/429/5xx → user sees retry message; no pack unless verification succeeds (default fail-closed).

**Acceptance Scenarios**:

1. **Given** Top.gg API returns timeout, 5xx, or rate limit, **When** I click **Vote & Claim Free Pack**, **Then** I see a friendly ephemeral message to try again in a few minutes — **no pack granted** (default).
2. **Given** Top.gg API is down, **When** ops has **not** enabled an emergency bypass flag, **Then** the bot does **not** silently grant packs without verification.
3. **Given** Top.gg returns malformed/unexpected payload, **When** verification runs, **Then** the claim is blocked and the error is logged server-side without exposing tokens.

---

### User Story 4 - Store UX & Copy (Priority: P2)

As a manager browsing `/store`, I understand that voting is required and see accurate button/timer states.

**Why this priority**: Reduces "broken button" reports and sets expectations.

**Independent Test**: `/store` embed field for Daily Gacha Pack mentions Top.gg vote requirement; button label reflects vote+claim when ready.

**Acceptance Scenarios**:

1. **Given** I open `/store`, **When** the gacha section renders, **Then** copy states that a **Top.gg vote** is required and shows cooldown or availability consistent with button state.
2. **Given** pack is claimable, **When** the hub view loads, **Then** the button label is **Vote & Claim Free Pack** (or equivalent approved copy).
3. **Given** pack is on cooldown, **When** the hub view loads, **Then** the button is disabled and the embed shows remaining time.

---

### Edge Cases

- **Vote on website, return to Discord**: Top.gg API must recognize the vote; user does not need to vote inside Discord.
- **Stale vote (>12h)**: Treated as no vote; prompt to vote again.
- **Missing `TOPGG_TOKEN` in deployment**: Fail closed with ops-visible log; managers see generic "verification unavailable" (not a crash loop).
- **Unregistered user**: Existing `ensure_registered` on `/store` — unchanged.
- **Wrong user on ephemeral view**: Existing `interaction_check` on `StoreHubView` — unchanged.
- **Pack generation fails after vote verified**: Vote must **not** be marked consumed if `claim_daily_pack` rolls back (atomic RPC).
- **Bot restarts mid-interaction**: Ephemeral view timeout (900s) already applies; no persistent store view registration required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The free pack claim path in `/store` MUST verify the invoking user's Top.gg vote **immediately before** granting a pack, using Top.gg's API with the user's Discord ID.
- **FR-002**: A vote MUST be considered valid only if Top.gg reports an active vote within the platform's **12-hour** window (or equivalent `nextVoteAt` / v0 `voted=1` semantics).
- **FR-003**: If the user has not voted or the vote is stale, the bot MUST show an ephemeral embed with the Top.gg vote link (`https://top.gg/bot/{bot_id}/vote`) and instruct the user to vote, then click the button again — **without** granting a pack.
- **FR-004**: The system MUST NOT introduce a new slash command, hub, or Store button — only extend the existing pack claim control (`store_gacha_claim`).
- **FR-005**: Successful pack claims MUST continue to use RPC `claim_daily_pack` for atomic cooldown + card insert; app code MUST NOT split cooldown update from card insert.
- **FR-006**: The server MUST record vote consumption server-side (column or log) so the same vote cycle cannot grant multiple packs.
- **FR-007**: Pack cooldown MUST align with the vote/claim window — default **12 hours** from successful claim (replacing the current 22-hour gate for this reward). Cooldown enforcement MUST remain in the RPC, not app-only.
- **FR-008**: On Top.gg API errors (timeout, 5xx, 429), the default behavior MUST be **fail closed** (no pack) with user-friendly retry messaging.
- **FR-009**: Optional ops-only emergency bypass via `game_config` MAY exist but MUST default **off** and MUST NOT be exposed in player UI.
- **FR-010**: `TOPGG_TOKEN` MUST live in environment config (`.env`); MUST NOT be logged or committed.
- **FR-011**: Player-facing changelog (`change_log.md`) and SDD US-02 MUST be updated when this ships.
- **FR-012**: Pack rarity/generation rules (Epic-capped mix, config override) MUST remain unchanged — only the vote gate is added.

### Non-Functional Requirements

- **NFR-001**: Vote API calls SHOULD use existing HTTP stack (`httpx` or `aiohttp` already in repo); no new dependency unless justified.
- **NFR-002**: Vote verification SHOULD complete within Discord interaction budget (defer already in place; target <10s including DB).
- **NFR-003**: Do not import `discord` or perform Top.gg HTTP from `packages/`.

### Key Entities

- **Top.gg vote status**: External state — user id, vote timestamp / next vote time, active/expired.
- **Vote consumption record**: Server-side marker tying a claim to a specific vote cycle (`last_vote_consumed_at` or dedicated log row).
- **Pack claim cooldown**: `players.last_claim_at` (duration updated to 12h default in RPC).
- **Daily pack claim**: Unchanged 5-card flow via `generate_pack` → `claim_daily_pack`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pack grants in test runs occur only after Top.gg API returns an active vote for that Discord user.
- **SC-002**: 0% double-pack grants from a single vote cycle in concurrent-click tests.
- **SC-003**: Managers without a vote always receive the vote-link prompt, never a pack.
- **SC-004**: Simulated Top.gg outage produces retry messaging with 0 unauthorized pack grants (fail-closed default).
- **SC-005**: `/store` embed and button copy audited — no promise of free pack without voting.

## Assumptions

- Top.gg **12-hour** vote window is the source of truth for "recent vote."
- Pack cooldown changes from **22h → 12h** to match vote/claim cadence (product decision; tunable later via `game_config` if ops wants 22h + fresh vote each time).
- Bot uses Top.gg **v1** `GET /projects/@me/votes/:user_id?source=discord`; v0 `/bots/:id/check` documented as fallback only.
- Vote consumption stored on `players` (e.g. `last_topgg_vote_at` consumed) or small log table — exact column chosen in plan phase.
- `StoreHubView` remains ephemeral (no `bot.add_view` registration).
- Daily login and energy refill buttons are unaffected.

## Out of Scope

- Top.gg webhook listener for automatic rewards (check-on-click only for v1)
- Paid packs or gem packs
- Voting rewards outside the free Store pack (coins, energy, etc.)
- Top.gg stats posting / server count auto-post
- Public website Top.gg page redesign (008)
- Requiring vote for matches, drills, or other hubs

## Dependencies

- Top.gg project API token (`TOPGG_TOKEN`) configured on Render/host
- Bot listed on Top.gg with correct Discord application ID
- New migration if RPC/columns change (vote consumption + cooldown interval)
