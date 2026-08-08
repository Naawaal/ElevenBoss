# Feature Specification: Competitive Bot Match Experience (NSS v3)

**Feature Branch**: `057-competitive-bot-match`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Enhance `/battle bot` so Bot Battles feel like complete competitive football matches: extra time, penalty shootouts, expanded match-day events, persistent red-card suspensions, fair dynamic AI difficulty, richer stats, restart-safe phases, and rate-limit-safe Discord presentation. Additive only; flag default off; no PvP/matchmaking/queues/rivalries/new commands."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extra Time After Drawn Regulation (Priority: P1)

As a manager playing `/battle bot` with Competitive Match enabled, I want a tied 90-minute match to continue into two short extra-time periods so that draws feel unresolved until the contest is properly decided or ready for penalties.

**Why this priority**: Extra time is the first visible upgrade that turns “90 minutes then done” into a competitive match arc, and it can ship without shootouts.

**Independent Test**: Enable the feature flag; force or seed a regulation draw; confirm two five-minute extra-time periods run with fitness/discipline carried forward; a decisive ET goal ends the match; flag-off behavior matches today’s Bot Battle.

**Acceptance Scenarios**:

1. **Given** Competitive Match is disabled, **When** a Bot Battle finishes, **Then** behavior matches today’s NSS Bot Battle with no extra phases.
2. **Given** Competitive Match is enabled and regulation ends with different scores, **When** the match resolves, **Then** it completes without extra time.
3. **Given** Competitive Match is enabled and regulation ends level, **When** regulation finishes, **Then** the match enters Extra Time First Half (minutes 91–95 in game time).
4. **Given** extra time is underway, **When** intervals continue, **Then** fitness and disciplinary state from minute 90 carry forward (no reset), with elevated fatigue and injury risk versus regulation.
5. **Given** a side takes the lead in extra time and that lead stands at the end of the second period, **When** extra time ends, **Then** the match completes with that football score (no shootout).

---

### User Story 2 - Penalty Shootout After Extra-Time Draw (Priority: P2)

As a manager whose Bot Battle is still level after extra time, I want a fair automatic penalty shootout so that the match reaches a decisive winner without manual kick/dive controls.

**Why this priority**: Shootouts complete the competitive arc after ET and are the second independently deliverable slice after the phase machine exists.

**Independent Test**: Seed an ET draw; confirm five kicks each with early stop when mathematically decided, then sudden death if needed; red-carded/substituted/unavailable players excluded; shootout goals do not change the football score display beyond “AET (pens)”.

**Acceptance Scenarios**:

1. **Given** the score is still tied after Extra Time Second Half, **When** that period ends, **Then** the match enters a penalty shootout.
2. **Given** a standard shootout, **When** one side can no longer be caught, **Then** remaining unnecessary kicks are not simulated.
3. **Given** both sides are level after five kicks each, **When** the shootout continues, **Then** sudden death proceeds with fair cycling of eligible takers.
4. **Given** a player was sent off or otherwise ineligible at the end of extra time, **When** takers are selected, **Then** that player cannot take a penalty.
5. **Given** a shootout finishes 5–4 after 3–3 AET, **When** the final result is shown, **Then** football score remains 3–3 and penalties are shown separately (e.g. 3–3 (5–4 pens)).

---

### User Story 3 - Restart-Safe Match Phases (Priority: P3)

As a manager mid–extra-time or mid-shootout when the bot restarts, I want the match to resume from the correct phase without replaying finished football or completed kicks so that long stadium sessions remain trustworthy.

**Why this priority**: Discord Bot Battles can span multiple updates; without recovery, ET/pens are not production-safe.

**Independent Test**: Persist mid-ET and mid-shootout states; restart; resume next interval/kick only; completed kicks unchanged; settlement still idempotent.

**Acceptance Scenarios**:

1. **Given** a match is in Extra Time First Half when the process restarts, **When** recovery runs, **Then** regulation is not resimulated and ET continues from saved phase/minute.
2. **Given** eight penalty kicks are already stored, **When** the bot recovers mid-shootout, **Then** only kick nine onward is simulated.
3. **Given** double recovery attempts on the same run, **When** settlement/kick continuation runs twice, **Then** no duplicate kicks or double rewards occur.
4. **Given** a commentary/Discord send fails, **When** simulation continues, **Then** football state is not rolled back or resimulated because of the presentation failure.

---

### User Story 4 - Red-Card Suspensions for Future Bot Battles (Priority: P4)

As a manager, I want straight reds and second-yellow dismissals to suspend the offender for upcoming Bot Battles so that discipline has lasting weight beyond a single match.

**Why this priority**: Persistent consequences deepen competitive feel; depends on dismissal events already produced by the engine.

**Independent Test**: Emit dismissal consequence → suspension created with correct length; next `/battle bot` blocks that card from the squad; after serving the required completed Bot Battles, eligibility returns.

**Acceptance Scenarios**:

1. **Given** a player receives a second-yellow dismissal in a Competitive Bot Battle, **When** the match settles, **Then** they are suspended for 1 future Bot Battle.
2. **Given** a player receives a straight red, **When** the match settles, **Then** they are suspended for 2 future Bot Battles.
3. **Given** a player has matches remaining on a suspension, **When** the manager tries to include them in `/battle bot`, **Then** squad validation blocks them using the existing validation surface (no new command).
4. **Given** a suspended player’s club completes an eligible Bot Battle, **When** settlement runs, **Then** remaining suspension matches decrement atomically with other settlement work.
5. **Given** Competitive Match is disabled, **When** Bot Battles run, **Then** no new suspension behavior is required beyond today’s discipline handling (or suspensions remain inert if none exist).

---

### User Story 5 - Richer Match Events Without Stadium Spam (Priority: P5)

As a manager watching the live stadium, I want fouls, free kicks, corners, and offsides reflected in stats and selective commentary, plus clear ET/penalty phase banners, without flooding Discord with low-value messages.

**Why this priority**: Realism and readability; can follow core phases once presentation buffering exists.

**Independent Test**: Run enabled matches; confirm expanded stats on the result; high-signal events always surface; routine events mostly stats-only; ET/pens use compact phase messages; shootout prefers one updating sequence over many new messages.

**Acceptance Scenarios**:

1. **Given** Competitive Match is enabled, **When** a match completes, **Then** post-match stats include corners, fouls, offsides, yellows, reds, whether ET was played, and penalty tallies when applicable.
2. **Given** regulation/ET/penalties transitions, **When** those phases start, **Then** managers see a small number of high-signal phase banners (not one message per interval).
3. **Given** a penalty shootout, **When** kicks resolve, **Then** the stadium shows a compact sequence (emoji/text) preferably on one reused message where practical.
4. **Given** routine corners/fouls/offsides, **When** they occur, **Then** they primarily update statistics and only occasionally appear in commentary.
5. **Given** goals, reds, major injuries, ET transitions, penalty kicks, and final whistle, **When** they occur, **Then** they always receive stadium attention.

---

### User Story 6 - Fair Dynamic Bot Difficulty (Priority: P6)

As a manager, I want the AI opponent to feel competitively close to my club’s strength without invisible super-players or rule-breaking advantages.

**Why this priority**: Improves long-term Bot Battle engagement after the match arc works; must not cheat economy or discipline rules.

**Independent Test**: Across club-strength bands, bot target strength stays within configured bounds of manager strength; AI still suffers fatigue, cards, and dismissals; no guaranteed goals/saves from rating alone.

**Acceptance Scenarios**:

1. **Given** dynamic difficulty is enabled, **When** a Bot Battle builds the AI side, **Then** its effective strength tracks the manager club within configured min/max deltas (plus optional offset).
2. **Given** an AI player is sent off or fatigued, **When** the match continues, **Then** the AI obeys the same rules as the human side.
3. **Given** shootouts and open play, **When** outcomes resolve, **Then** the AI receives no special scoring or save bonuses beyond the shared quality model.

---

### Edge Cases

- Player sent off in extra time: removed immediately, cannot be replaced for the red, cannot take penalties, earns suspension.
- Goalkeeper sent off: shootout uses whoever legally keeps goal at end of ET under existing emergency-GK/sub rules.
- Injured/removed players: ineligible for penalties; “play on” players may remain eligible but at reduced quality from fitness.
- Side with fewer eligible takers: cycles its own eligible list; opponent is not forced to the same count.
- Early mathematical shootout win: stop immediately.
- Stadium thread deleted: simulation/settlement continues; post-match uses existing Battle fallback delivery.
- Economy: ET/pens do not create a second reward pipe; penalty kicks grant no XP; settlement stays idempotent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When Competitive Match is disabled, `/battle bot` MUST behave identically to the current NSS Bot Battle experience.
- **FR-002**: Competitive Match MUST be entered only through existing `/battle bot` (and its current hub button); no new slash commands, hubs, or player-facing config surfaces.
- **FR-003**: When enabled and regulation ends level, the match MUST enter two extra-time periods of five in-game minutes each (91–95 and 96–100).
- **FR-004**: Extra time MUST reuse the existing interval simulation (strength, chance creation, tactics, momentum, XI, discipline, subs, injuries, fitness) — not a separate scoring model.
- **FR-005**: Fitness and discipline MUST carry from regulation into extra time without reset; ET MUST apply configurable elevated fatigue and injury multipliers.
- **FR-006**: When still level after the second ET period, the match MUST enter a penalty shootout of up to five kicks each, with early stop and sudden death as needed.
- **FR-007**: Shootout goals MUST NOT be added to the football score; final presentation MUST distinguish regulation / AET / penalties.
- **FR-008**: Penalty taker quality MUST use shooting, derived composure (from consistency/morale — no new permanent card attributes), fitness, and consistency; keepers MUST use effective defensive strength as reflexes basis plus fitness/consistency.
- **FR-009**: Conversion probabilities MUST stay bounded (no guaranteed goal/save at max ratings); calibration target roughly 58–90% scoring chance depending on quality gap.
- **FR-010**: Ineligible players (sent off, substituted out, unable to continue) MUST be excluded from shootouts; taker order MUST be fair and cycle before repeats when possible.
- **FR-011**: Existing yellow / second-yellow / straight-red discipline MUST remain authoritative; ET has no special exceptions.
- **FR-012**: Straight red and second-yellow dismissals MUST create future Bot Battle suspensions (2 and 1 matches respectively) enforced at squad selection and decremented atomically on eligible match settlement.
- **FR-013**: Cross-match yellow-card accumulation is OUT of scope for Phase 1; match summaries may still show yellows.
- **FR-014**: Fouls, free kicks, corners, and offsides MUST appear in match statistics; only noteworthy instances enter public commentary.
- **FR-015**: Match results MUST expose extended stats (corners, fouls, offsides, cards, ET played, penalty tallies/winner when applicable) without removing existing stats.
- **FR-016**: Matches MUST be deterministic for identical seed and config, including shootout kick sequences.
- **FR-017**: Matches MUST recover safely from restarts in regulation completion, either ET period, and any shootout/sudden-death point without resimulating completed football or kicks.
- **FR-018**: Competitive AI strength MUST be bounded relative to manager club strength; AI MUST NOT receive invisible max-rated players, ignore fatigue/cards, or get shootout bonuses.
- **FR-019**: Discord presentation MUST batch or suppress low-value events; ET/pens use compact phase messaging; shootouts prefer one updating sequence where practical.
- **FR-020**: Competitive resolution MUST NOT introduce a second XP/coin/evolution/fatigue settlement pipeline; Phase 1 keeps existing reward policy (no penalty-kick XP; ET volume does not create extra reward opportunities).
- **FR-021**: Feature MUST default OFF via config/env (`competitive_match_enabled` / `COMPETITIVE_MATCH_ENABLED`) with immediate rollback by turning the flag off.
- **FR-022**: The feature MUST NOT include PvP, matchmaking, queues, rivalries, ghost managers, VAR, weather, handballs, manual pen direction/dive selection, or permanent new player attributes.
- **FR-023**: All simulation math MUST remain pure (no Discord/DB) in the match engine packages; Discord and persistence remain adapters.

### Key Entities

- **Match Phase**: Regulation → Extra Time First → Extra Time Second → Penalty Shootout → Complete.
- **Football Score vs Penalty Score**: Separate tallies; pens never inflate the football scoreline.
- **Penalty Shootout State**: Serializable kick progress (taken/scored, indices, sudden death, winner, kick events) for recovery.
- **Player Suspension**: Persistent red-card consequence (reason, source match, matches remaining) enforced on future Bot Battles.
- **Competitive Feature Flag**: Global enable switch defaulting off.
- **Derived Composure / Reflexes**: Virtual ratings for shootouts only, derived from existing player inputs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the flag off, 100% of Bot Battle acceptance checks match the pre-feature baseline (scores, settlement, message pattern).
- **SC-002**: With the flag on, 100% of regulation draws enter two ET periods; decisive ET ends without pens; ET draws enter shootouts.
- **SC-003**: In calibrated shootout samples, scoring rate falls roughly in the 68–82% band; no max-rated auto-goal/auto-save cases.
- **SC-004**: 100% of mid-ET and mid-shootout recovery tests resume without duplicating completed intervals/kicks or double-settling rewards.
- **SC-005**: 100% of second-yellow and straight-red cases create the correct Bot Battle suspension lengths and block squad selection until served.
- **SC-006**: Stadium commentary for competitive matches stays within the project’s safe live-update cadence (no sustained one-message-per-low-value-event pattern; no material spike in rate-limit incidents vs baseline in controlled enablement).
- **SC-007**: Economy regression suite shows zero duplicate XP/coins/evolution ticks and zero penalty-kick XP when the flag is on.
- **SC-008**: Across weak/equal/strong club bands, Bot Battle win distributions show no obviously exploitable mismatch attributable to AI cheating.
- **SC-009**: Managers never need a new command: 100% of competitive Bot Battles still start from existing `/battle bot` / hub Bot Battle control.
- **SC-010**: Feature can be disabled in production within one config/env change and immediately restores baseline Bot Battle behavior for new matches.

## Assumptions

- Entry point is **Bot Battle only** (`/battle bot`); Friendly and League modes are unchanged unless later explicitly scoped.
- Extra time is an ElevenBoss abstraction (5+5), not a literal 15+15 real-world clock.
- Composure and GK reflexes are **derived** for v1; no schema change for permanent attributes.
- Yellow accumulation across matches is deferred; only red-based suspensions ship in the first persistence slice.
- Initial settlement keeps today’s coin/XP/Division Rank policy for ET/pens until calibration justifies a separate reward discussion.
- Existing NSS discipline, injuries, substitutions, set pieces, stadium thread, match runs, and settlement RPCs are extended — not replaced.
- Rollout is phased (ET → pens → events → suspensions → UI → AI → shadow → controlled enable → default on) with the flag remaining the kill switch.
- Detailed engine file layout, RPC shapes, migration numbering, and the nine-phase rollout checklist belong in `/speckit-plan`; this specification defines product behavior and acceptance.
- No PvP/matchmaking work is in scope (consistent with Feature 056 shelving).
- Calibration bands in the source brief (draw rate, ET resolution rate, etc.) guide Phase 7–9 gates and will be formalized in the plan’s verification artifacts.
