# Feature Specification: Ranked PvP Matchmaking and Manager Rivalries

**Feature Branch**: `053-pvp-matchmaking-rivalries`  
**Created**: 2026-08-04  
**Status**: Planned (implementation gated on 052 ACCEPT)  
**Priority**: P1 engagement  
**Input**: User description — replace reward-bearing Bot Battle with guild-local Ranked PvP; convert AI to Practice (no competitive points); add rivalry tracking from repeated ranked meetings; keep Friendly as sandbox; no new top-level slash commands.

**Implementation gate**: Feature **052** MUST reach formal **ACCEPT** (Monday YA V2 soak complete) before `/speckit.plan` coding or migration work for 053. Specification and planning docs may exist earlier; **no production gameplay ship**.

**Delivery model**: Two vertical slices — (1) Ranked PvP + AI Practice conversion, (2) Rivalries.

**Primary surface**: Existing `/battle` hub only. **No** new top-level slash command.

---

## Problem Statement

Managers currently earn competitive progression and meaningful rewards primarily against bots. That undercuts human competition, Global LP meaning, and social drama. Friendly already proves two humans can share a live stadium thread, but it is deliberately a rewardless sandbox.

ElevenBoss needs a **guild-local Ranked PvP** mode that:

1. Pairs two eligible human managers in the same Discord server  
2. Reuses the live stadium / commentary / pitch experience  
3. Awards coins, player XP, and Global LP only for Ranked PvP  
4. Builds persistent rivalries from repeated ranked meetings  

AI remains available as **AI Practice** — useful for onboarding and casual play, but **never** competitive.

---

## Core Product Rules

### Ranked PvP is the only competitive `/battle` mode

Only Ranked PvP may change Global LP / global division, PvP W-D-L, ranked leaderboard position, rivalry records/streaks/badges, and competitive milestones.

### AI Practice awards no competitive points

AI Practice always awards **0** Global LP, **0** league points, **0** PvP rating movement, **0** rivalry progress, and **0** competitive record changes. It may award limited coins and player XP under capped rules.

### Friendly remains sandbox

Friendly stays free: no energy, coins, XP, LP, rivalry, injuries/fatigue, or competitive stats. Ranked PvP is a **separate** competitive path — Friendly’s contract must not change.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Find and play a ranked human opponent (Priority: P1)

As a manager, I open `/battle`, press **Find Opponent**, wait in a short same-guild queue, get paired with another eligible human, share one stadium thread, and finish a live match that awards competitive rewards and Global LP.

**Why this priority**: This is the engagement replacement for Bot Battle as the competitive loop.

**Independent Test**: Two eligible managers in one guild join Find Opponent, get paired within search rules, share one thread, complete one match; both receive one reward/LP finalization; AI is never substituted silently.

**Acceptance Scenarios**:

1. **Given** Ranked PvP is enabled and I am eligible, **When** I press Find Opponent, **Then** I enter searching with no energy spent yet and can Cancel.
2. **Given** another eligible manager is searching in the same guild, **When** matchmaking pairs us, **Then** we both see Opponent Found and one shared stadium opens without a second ready confirm.
3. **Given** search reaches the timeout (~60s) with no pair, **When** I am prompted, **Then** I must explicitly choose Continue Search, AI Practice, or Cancel — never silent AI.
4. **Given** kickoff fails (e.g. stadium cannot open), **When** the attempt aborts, **Then** neither manager loses energy, rewards, or LP, and locks are released.
5. **Given** a Ranked PvP match completes, **When** results finalize, **Then** coins/XP/LP/career PvP stats apply exactly once per manager through the normal reward pipes.

---

### User Story 2 — Compete for Global LP only through Ranked PvP (Priority: P1)

As a competitive manager, only Ranked PvP moves my Global LP and division; Practice and Friendly never do.

**Why this priority**: Protects ladder integrity and anti-farming.

**Independent Test**: Complete one PvP, one Practice, one Friendly; only PvP shows non-zero Global LP delta and division movement.

**Acceptance Scenarios**:

1. **Given** a Ranked PvP result, **When** finalized, **Then** Global LP changes using existing relative-rating style rules (including provisional protection for early ranked matches).
2. **Given** an AI Practice result, **When** finalized, **Then** Global LP delta is 0 and PvP record / rivalry are unchanged.
3. **Given** a Friendly result, **When** finalized, **Then** no coins, XP, LP, rivalry, or competitive stats change (existing sandbox preserved).
4. **Given** scheduled guild league fixtures, **When** they resolve, **Then** they remain on their existing policy and are not treated as Ranked PvP matchmaking.

---

### User Story 3 — Use AI Practice without competitive progress (Priority: P1)

As a new or casual manager, I can still play AI Practice from `/battle` with reduced/capped progression and clear “No Global LP” messaging.

**Why this priority**: Softens the Bot Battle removal and supports onboarding.

**Independent Test**: New vs established Practice reward paths; daily Practice reward cap; embeds state no Global LP; Practice cannot update rivalries.

**Acceptance Scenarios**:

1. **Given** I choose AI Practice (including after queue timeout), **When** the match completes, **Then** energy/coins/XP follow Practice policy and competitive fields stay zero.
2. **Given** I am an established manager, **When** I finish rewarded Practice matches, **Then** daily rewarded Practice is capped (default two per UTC day).
3. **Given** legacy Bot Battle naming, **When** I open `/battle`, **Then** the primary competitive CTA is Find Opponent and AI is labeled Practice (rollback may restore legacy presentation behind a flag).

---

### User Story 4 — Trust fair guild-local matchmaking (Priority: P1)

As a manager, I only queue against humans in my Discord guild, within widening skill bands, with anti-rematch and daily limits that reduce win-trading.

**Why this priority**: Discord thread sharing forces guild-local MVP; fairness is the trust layer.

**Independent Test**: Cross-guild pairing impossible; blocked pairs excluded; same-pair cooldown/daily limits enforced; after daily ranked cap I cannot rejoin until UTC reset.

**Acceptance Scenarios**:

1. **Given** I am searching, **When** the only other searcher is in another guild, **Then** we are not paired.
2. **Given** search time increases, **When** widening steps apply, **Then** division / LP / XI OVR bands expand per the published schedule (same division ±100 LP ±4 OVR first; up to configured maxima later).
3. **Given** I already played this opponent ranked recently, **When** matching runs, **Then** we are excluded until cooldown/daily pair limits allow.
4. **Given** I completed the daily ranked PvP cap (default 5), **When** I try Find Opponent, **Then** I am blocked until UTC day reset.
5. **Given** I change my squad while queued, **When** a pair is claimed, **Then** eligibility is rechecked authoritatively and invalid/manipulated entries are rejected.

---

### User Story 5 — Build rivalries from repeated ranked meetings (Priority: P2)

As a manager, repeated Ranked PvP against the same opponent automatically tracks head-to-head and becomes an active rivalry after enough recent meetings, with presentation and a Rivalries hub — without changing the match simulation.

**Why this priority**: Social narrative; depends on reliable Ranked PvP finalization (slice 2).

**Independent Test**: Three ranked meetings within 30 days activate rivalry; Friendly/Practice never count; rivalry UI shows records; simulation odds unchanged.

**Acceptance Scenarios**:

1. **Given** two ranked meetings between the same pair, **When** I view Rivalries, **Then** the pair is tracking (not yet active).
2. **Given** a third ranked meeting within 30 days, **When** the match finalizes, **Then** rivalry becomes active and both managers see a rivalry update at full time.
3. **Given** 60 days without a ranked meeting, **When** status refreshes, **Then** rivalry becomes dormant but history remains.
4. **Given** a rivalry match, **When** commentary/embeds mention the series, **Then** presentation-only — no attribute, probability, reward, or LP formula change.
5. **Given** Rivalries hub, **When** I choose Friendly Rematch, **Then** Friendly opens and does **not** update ranked rivalry.

---

### User Story 6 — Control privacy and blocked opponents (Priority: P2)

As a manager, I can block another manager and tune rivalry notifications/visibility without erasing historical competitive integrity.

**Why this priority**: Toxicity safeguards for live PvP.

**Independent Test**: Block prevents ranked matching and Friendly invites both ways for the pair; historical results remain stored; no “rival logged in” presence alerts.

**Acceptance Scenarios**:

1. **Given** I block a manager, **When** either of us searches ranked, **Then** we cannot be paired.
2. **Given** a block exists, **When** either sends Friendly Challenge, **Then** it is rejected.
3. **Given** I disable rivalry DMs or callouts, **When** a rivalry result occurs, **Then** those surfaces respect the preference.
4. **Given** this release, **When** looking for presence/login rival alerts, **Then** none exist.

---

### User Story 7 — Recover safely across restarts and failures (Priority: P1)

As a manager (and as ops), queue and match state survive bot restarts without duplicate rewards or silent energy charges.

**Why this priority**: Dual-human money/LP integrity.

**Independent Test**: Restart while queued; restart mid-run; duplicate finalize attempts; abandoned pre-kickoff paths.

**Acceptance Scenarios**:

1. **Given** I am searching and the bot restarts, **When** I reopen `/battle`, **Then** my queue state is visible or cleanly expired — no energy lost.
2. **Given** a PvP run exists after restart, **When** recovery runs, **Then** the same seed/result finalizes at most once for both managers.
3. **Given** finalization is retried, **When** the second attempt runs, **Then** no duplicate coins, XP, or LP.

---

### Edge Cases

- One manager leaves the Discord server after kickoff: match still resolves; delivery falls back to DM / Battle history when possible.
- Both managers disconnect: server-owned simulation continues.
- No second eligible manager in the guild: timeout choices only; no forced AI.
- Energy sufficient at join but not at pair claim: claim fails; no charge.
- Feature flag off: Find Opponent hidden/disabled; legacy Bot Battle presentation available for rollback soak window.
- Ranked PvP does not update scheduled guild-league standings.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose Ranked PvP, Friendly Challenge, AI Practice, Rivalries, and Match History from the existing `/battle` hub without adding a new top-level slash command.
- **FR-002**: Ranked matchmaking MUST be guild-local only (same Discord guild for both managers and the stadium thread).
- **FR-003**: Joining the ranked queue MUST NOT spend energy; energy MUST be charged only on successful competitive finalization paths defined for that mode.
- **FR-004**: Search MUST default to ~60 seconds then require an explicit Continue / AI Practice / Cancel choice — never silent AI substitution.
- **FR-005**: Matchmaking MUST widen eligibility over time per product schedule and pick the best pair by wait, division gap, LP gap, then XI rating gap.
- **FR-006**: Pair claim MUST revalidate eligibility (squad, energy, locks, caps, blocks) authoritatively before creating a match.
- **FR-007**: Same-pair ranked cooldown (default 30 minutes), same-pair daily ranked limit (default 2), and per-manager daily ranked cap (default 5) MUST be enforced; after the daily ranked cap, requeue is blocked until UTC reset.
- **FR-008**: Pre-kickoff failure MUST abandon cleanly with no energy, rewards, or LP and with locks released.
- **FR-009**: Ranked PvP MUST reuse the existing live stadium presentation (pitch, commentary, injuries/fatigue display, full-time summary) without live mid-match tactical buttons in this release.
- **FR-010**: Only Ranked PvP (`pvp`) MAY apply non-zero Global LP; Practice and Friendly MUST always finalize with zero competitive LP and must not update rivalries or PvP competitive records.
- **FR-011**: Ranked rewards (coins, XP, fatigue/injuries, LP) MUST use existing economy/XP/match pipelines — no client-supplied result, LP, or reward amounts; finalize exactly once per manager per run.
- **FR-012**: AI Practice MUST use reduced/capped progression (new vs established multipliers and daily rewarded Practice cap) and MUST display that Global LP is not awarded.
- **FR-013**: Friendly MUST remain a rewardless sandbox and MUST NOT be usable for ranked win-trading.
- **FR-014**: There MUST be no direct Ranked challenge in MVP; Friendly Challenge remains the only direct invite path.
- **FR-015**: Rivalries MUST track ranked meetings only; activate after 3 ranked meetings within 30 days; dormancy after 60 days without ranked meeting; history retained.
- **FR-016**: Rivalry presentation MUST never alter simulation probabilities, attributes, rewards, fitness, injuries, or LP math.
- **FR-017**: Managers MUST be able to block others (blocks ranked matching and Friendly invites) and control rivalry DM/callout/leaderboard visibility preferences.
- **FR-018**: System MUST NOT implement rival login/presence notifications.
- **FR-019**: Ranked PvP MUST be disableable via authoritative feature flag without deleting completed history, LP already applied, or rivalry records; legacy Bot Battle path remains available for rollback during soak.
- **FR-020**: Cross-server PvP, mirrored stadiums, live tactics, wagering, new PvP currency, tournaments, clan battles, and rivalry gameplay bonuses are out of scope for this release.

### Key Entities

- **Ranked Queue Entry**: A manager’s search for a same-guild human opponent (status, skill snapshot, expiry).
- **Ranked PvP Match**: A human-vs-human competitive match with shared stadium, deterministic simulation, dual rewards, and LP.
- **AI Practice Match**: Human-vs-AI non-competitive match with capped progression and zero LP/rivalry.
- **Friendly Match**: Existing sandbox human invite path.
- **Manager Rivalry**: Canonical pair record of ranked meetings, series scores, streaks, activation/dormancy.
- **Manager Block**: Preference preventing ranked pairing and Friendly between two managers.
- **Battle Hub State**: Snapshot of flags, queue, energy costs, daily caps, LP/division, rivalries, unresolved matches.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In acceptance tests, two eligible same-guild managers can complete Find Opponent → shared stadium → single dual finalization with Ranked rewards and LP.
- **SC-002**: 100% of Practice and Friendly acceptance runs show Global LP delta 0 and no rivalry / PvP competitive record updates.
- **SC-003**: Cross-guild automatic pairing rate is 0 in tests and soak.
- **SC-004**: Silent AI substitution after ranked timeout is 0 — every timeout requires an explicit user choice.
- **SC-005**: Duplicate finalization attempts produce no second coin/XP/LP grant (≥95% of harness retries; target 100% for P0 money paths).
- **SC-006**: Same-pair cooldown and daily ranked caps block rematch/farm paths in automated tests.
- **SC-007**: After three ranked meetings within 30 days, rivalry status becomes active and appears in Rivalries UI for both managers.
- **SC-008**: With `battle_pvp_enabled = false`, managers cannot join ranked queue; rollback presentation remains available.
- **SC-009**: Internal/selected-guild soak completes with no P0/P1 defects (duplicate rewards, lock leaks, cross-mode LP leaks, silent AI).
- **SC-010**: Managers can open the full Ranked + Practice + Friendly loop from `/battle` with no new top-level command.

---

## Assumptions

- Feature 052 YA V2 formal ACCEPT lands before 053 implementation/coding.
- Existing Friendly dual-human stadium patterns, match locks, V3 engine, XP/economy RPCs, and Global LP helpers are reused rather than replaced.
- Guild-local matching is acceptable MVP because Discord thread sharing is required for both managers.
- Default numeric balance (energy 20 PvP / 10 Practice, coin multipliers, daily caps, search bands, rivalry 3/30/60) is product-approved starting config and remains tunable without a new feature.
- No live mid-match tactics in MVP.
- Provisional LP protection applies for the first N ranked matches (default 5).
- Rivalry badges reuse existing badge/achievement infrastructure with no gameplay bonuses.

---

## Out of Scope

- Cross-server / mirrored-thread PvP  
- Manual ranked challenges  
- Live tactical inputs during play  
- Wagering, new currency, paid matchmaking  
- Clan battles, brackets, spectator bonuses  
- Rival presence/login notifications  
- Rivalry stat boosts or reward farming  
- Separate PvP seasons / ML anti-cheat  
- Changing Friendly into a rewarded mode  

---

## Dependencies

- Feature 052 formal ACCEPT (implementation gate)  
- Existing `/battle` hub, Friendly human-vs-human stadium flow, match-run lifecycle, locks, V3 simulation, commentary/pitch  
- Global LP / division helpers  
- Economy (`apply_club_economy`) and match XP (`process_match_result` / single XP pipe)  
- Existing badge/achievement surface for rivalry badges  
- Feature flag + `game_config` rollout controls  

---

## Notes for planning (non-normative)

Detailed queue schemas, RPC names, scheduler intervals, and task breakdowns from the proposal belong in `/speckit.plan` and `/speckit.tasks` **after** the 052 gate. Planned migration placeholder: `098_pvp_matchmaking_rivalries.sql` (renumber if head advances). Slice 1 = Ranked PvP + Practice conversion; Slice 2 = Rivalries.
