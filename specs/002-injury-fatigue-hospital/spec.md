# Feature Specification: Player Fatigue, Injury, Bench & Hospital

**Feature Branch**: `002-injury-fatigue-hospital`

**Created**: 2026-07-11

**Status**: Draft (clarifications resolved 2026-07-11 — Q1/Q2/Q3 = A)

**Input**: User description: "Integrate Player Fatigue, Injury, Bench, and Healthcare (Hospital) per GDD; audit existing systems and produce an Integration Blueprint before implementation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-Player Fatigue Affects Match Performance (Priority: P1)

As a manager, my players accumulate fatigue from matches and recover over real time. Fatigued starters perform worse in matches, so I must rotate my squad instead of always fielding the same XI.

**Why this priority**: Fatigue is the foundation for injury risk and squad rotation. It delivers value without requiring hospital UI or in-match pauses, and can ship as a standalone MVP.

**Independent Test**: Play several bot/league matches with the same starting XI; confirm fatigue drops, match performance indicators worsen below defined thresholds, and fatigue recovers over real time without spending club action energy.

**Acceptance Scenarios**:

1. **Given** a fully rested starter (fatigue 100), **When** they complete a competitive match, **Then** their fatigue decreases by an amount based on physical attribute, tactic stance, and opponent strength.
2. **Given** a starter with fatigue in a penalty tier (e.g. below 75), **When** they play a match, **Then** their effective match contribution is reduced according to published fatigue penalty tiers.
3. **Given** a player sat on the bench for a full match, **When** the match ends, **Then** they recover a fixed amount of fatigue (bench rest), not drain.
4. **Given** time passes with no match, **When** passive recovery applies, **Then** fatigue increases toward 100 without consuming club action energy or energy-refill purchases.
5. **Given** a manager views squad or player profile, **When** fatigue is below full, **Then** a clear fatigue indicator is visible.

---

### User Story 2 - Injuries Persist and Block Compromised Play (Priority: P2)

As a manager, players can get injured from matches. Injured players are marked unavailable (or heavily compromised if forced), recover over days, and I can see expected return dates so I plan lineups around absences.

**Why this priority**: Injuries create meaningful squad management after fatigue exists. Post-match injury resolution is lower risk than live mid-match pause UI.

**Independent Test**: Force or simulate an injury outcome after a match; confirm the card shows injured status, cannot be freely used as a healthy starter without clear penalties/blocks, and recovers after the expected period.

**Acceptance Scenarios**:

1. **Given** a competitive match completes with one or more injury outcomes, **When** post-match processing runs, **Then** affected cards receive an injury tier, injury date, and expected recovery window.
2. **Given** a card is injured, **When** the manager opens squad selection, **Then** the card is clearly marked injured and cannot be placed in the starting XI as a healthy player (or is blocked per approved rule).
3. **Given** a card is injured, **When** the manager tries to assign them to a development drill, **Then** the action is blocked with a clear message.
4. **Given** recovery time elapses (hospital or untreated), **When** daily recovery processing runs, **Then** the injury clears and the card returns to available status.
5. **Given** an injury tier roll lands on 100 (formerly “career-ending”), **When** v1 injury resolution runs, **Then** the outcome is treated as **Major** (no auto-retire); the manager sees a Major injury, not card destruction.

---

### User Story 3 - Hospital Facility Speeds Recovery (Priority: P2)

As a manager, I can upgrade a Hospital facility under Club Facilities. Higher levels add beds and shorten injury recovery. Injured players auto-admit when beds are free; when full, I choose who to treat.

**Why this priority**: Hospital is the economic sink and recovery lever that makes injuries manageable. It extends the existing facilities hub rather than inventing a new command surface.

**Independent Test**: Upgrade Hospital one level; admit an injured player; confirm bed count and faster expected return vs untreated recovery; overflow when beds are full prompts a choice.

**Acceptance Scenarios**:

1. **Given** a club with Hospital level N and free beds, **When** a player is injured post-match, **Then** they are auto-admitted and recovery uses the hospital multiplier for that level.
2. **Given** all beds are occupied, **When** a new injury occurs, **Then** the manager is prompted to discharge someone, leave the new injury untreated, or otherwise resolve overflow.
3. **Given** the manager can afford the next Hospital upgrade and is off weekly facility cooldown, **When** they upgrade from Club Facilities, **Then** coins are spent, level increases, and bed capacity / recovery speed update.
4. **Given** a Hospital upgrade is purchased, **When** the RPC succeeds, **Then** the new level applies immediately (no multi-day build timer in v1 — same pattern as YA/TG); existing patients keep their already-computed expected recovery dates unless a later design adds recalculation.
5. **Given** Hospital costs and pacing, **When** compared to Youth Academy / Training Ground, **Then** costs use the approved premium facility ladder **1,500 / 4,000 / 10,000 / 25,000 / 60,000** coins and share the weekly facility upgrade slot.

---

### User Story 4 - In-Match Injury Stoppage & Bench Substitution (Priority: P3)

As a manager, when a player is injured during a live match (before the 90th minute), play pauses at the next natural stoppage and I pick a bench replacement within 30 seconds—or the system auto-picks. Edge cases (no subs left, GK injury, simultaneous injuries) behave predictably.

**Why this priority**: Highest Discord/UX complexity. Valuable, but depends on fatigue, injury persistence, and a real bench list being passed into the live match. Recommended as a later phase after P1–P2 are stable.

**Independent Test**: Trigger an in-match injury before 90'; confirm stoppage prompt, successful sub, Play On penalties, timeout auto-pick, and 10-men / emergency GK behaviors.

**Acceptance Scenarios**:

1. **Given** an injury occurs before minute 90 and subs remain, **When** the next stoppage is reached, **Then** the manager sees a substitution prompt with bench options sorted by readiness.
2. **Given** the manager selects a replacement within 30 seconds, **When** the choice is confirmed, **Then** the injured player leaves the pitch state and the substitute continues the match.
3. **Given** no response within 30 seconds, **When** the timeout fires, **Then** the best available bench player (by overall, respecting position rules) is auto-selected.
4. **Given** all substitution allowances are used, **When** another injury occurs, **Then** no sub prompt appears; the side continues weakened (10 effective players) and the injury is logged for post-match care.
5. **Given** the GK is injured and no GK is on the bench, **When** the manager must continue, **Then** an outfield emergency keeper is allowed with a severe effectiveness penalty.
6. **Given** two injuries in the same phase, **When** prompts are shown, **Then** they are resolved sequentially (one after the other).
7. **Given** an injury at minute 90+, **When** the match is ending, **Then** no substitution prompt appears; the injury is recorded for post-match processing only.
8. **Given** Phases 1–2 are shipped, **When** Phase 3 is implemented, **Then** this user story is delivered in an isolated PR per [plan-phase3.md](./plan-phase3.md) (pause via `async for` wait + `MatchState` mutation — not `generator.send()`).

---

### Edge Cases

- Club action energy is empty but players are fully rested — manager still cannot start energy-gated matches; fatigue does not replace energy.
- All bench players are injured or exhausted — auto-pick and lineup rules must fail gracefully with clear messaging.
- Bot-controlled / auto-sim league fixtures — injuries and fatigue still apply without interactive Discord prompts (auto-resolve subs / Play On rules).
- Friendly matches — [Assumption: friendlies remain sandbox; no fatigue drain, no injuries, no hospital admits unless later approved].
- Hospital full + DMs disabled — overflow prompt must fall back to an in-hub Hospital panel action, not silent failure.
- Double-tap upgrade / double admit — RPCs must be idempotent or reject duplicates safely.
- Player sold/fused while in hospital — admission must clear or block the destructive action with a clear error.
- Season aging / youth intake Monday jobs — recovery job must not conflict with or skip aging.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST track per-player-card fatigue on a 0–100 scale, defaulting existing cards to 100.
- **FR-002**: System MUST drain fatigue for starters after competitive matches using the approved drain formula (base drain, PHY mitigation, tactic modifier, intensity modifier).
- **FR-003**: System MUST apply fatigue-based performance penalties in competitive match simulation by tier (75–100 / 50–74 / 25–49 / 1–24 / 0).
- **FR-004**: System MUST recover fatigue passively over real time and grant bench-rest recovery for unused squad members who sat a match.
- **FR-005**: Club action energy MUST remain the club-level activity gate; fatigue MUST NOT replace, refill, or bypass action energy or energy-refill purchases.
- **FR-006**: System MUST roll injury chance for competitive matches using fatigue, age, and PHY modifiers, and assign injury tiers Minor / Moderate / Major only in v1 (tier-weight roll 100 maps to Major — no career-ending auto-retire).
- **FR-007**: System MUST persist injury status on the player card and expose expected recovery to the manager in profile/squad/hospital views.
- **FR-008**: Injured cards MUST be blocked from development drills and from being treated as healthy starters.
- **FR-009**: System MUST provide a Hospital facility (levels 0–5) with bed capacity `level + 1` and recovery-time multiplier `1 / (1 + 0.2 * level)`.
- **FR-010**: Hospital upgrades MUST spend coins through the existing club economy pipe and appear in the existing Club Facilities hub (no new top-level slash command required for v1).
- **FR-011**: Post-match, injured players MUST auto-admit when beds are available; overflow MUST prompt the manager.
- **FR-012**: System MUST process daily (or scheduled) recovery for fatigue and injury discharge in batch.
- **FR-013**: *(Phase 3 — planned)* Live competitive matches MUST pause at a natural stoppage when an interactive injury is pending, present a 30s bench select (plus Play On), and resume with the chosen outcome via `MatchState` mutation (no `generator.send()`); timeout auto-picks best overall eligible bench player. **Not required for Phases 1–2 (shipped).**
- **FR-014**: *(Phase 3 — planned)* Edge rules for live stoppages (no subs / empty bench → 10-men / emergency GK / sequential prompts / 90+ / AI auto-resolve) MUST ship with FR-013. **Not required for Phases 1–2 (shipped).**
- **FR-015**: Cosmetic-only injury ticker lines MUST be replaced or upgraded so injuries that matter also change card state (no “fake injury” that never persists). Phase 3: mid-match A+C rolls are authoritative; post-match persists `recorded_injuries` and MUST NOT double-roll when recordings exist.
- **FR-016**: Terminology in player-facing copy MUST use coins (not dollars) and Hospital as a Club Facility (not a separate currency building).

### Key Entities

- **Player Card Fitness**: Per-card fatigue (0–100), optional injury tier, injury timestamps, hospital admission flag — owned by a club/manager.
- **Club Hospital**: Facility level on the club, bed capacity, recovery multiplier, shared weekly upgrade cadence with other facilities unless otherwise approved.
- **Hospital Admission**: Link between an injured card and a bed; admission/expected discharge/actual discharge.
- **Match Injury Event**: In-match or post-match record of who was hurt, tier, minute, and whether Play On / sub / auto-resolve occurred.
- **Bench Snapshot**: Pre-match list of eligible substitutes (reserves not in starting XI), used for sub prompts and auto-picks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After one competitive match, every starter’s fatigue changes from the pre-match value in a way a manager can see in squad/profile within the same session.
- **SC-002**: Managers can distinguish rested vs fatigued vs injured players in squad view without opening external tools (visual indicators present for each state).
- **SC-003**: An injured player’s expected return is visible within 10 seconds of opening profile or Hospital panel.
- **SC-004**: With a free hospital bed, ≥95% of post-match injuries auto-admit without requiring a manual send action.
- **SC-005**: When the hospital is full, 100% of overflow cases present a resolvable choice (DM or Hospital panel fallback)—none fail silently.
- **SC-006**: Hospital upgrade costs and pacing keep Hospital as a long-term sink without making Youth Academy / Training Ground obsolete (managers still upgrade YA/TG under the shared facility rules).
- **SC-007**: Club action energy spend/refill behavior for matches and drills remains unchanged by fatigue recovery (no accidental free energy or double resource).
- **SC-008**: *(Phase 3 — planned)* For live injury stoppages, managers complete or auto-resolve the sub decision within 30 seconds without the match thread hanging indefinitely.
- **SC-009**: Auto-sim / bot-opponent matches still complete end-to-end when fatigue/injury apply (no human prompt on non-interactive paths; Phase 3 auto-resolve for AI/silent sims).

## Assumptions

- Fatigue and injury persist on **player cards**, not on the club/manager row used for coins and action energy.
- Competitive matches = bot battles and league matches; friendlies stay sandbox (no fatigue/injury) unless later approved.
- Hospital is a third Club Facility under `/store` → Club Facilities, extending `upgrade_club_facility`, not a new `/hospital` command for v1.
- **Resolved Q1 (A):** Hospital upgrade costs = **1,500 / 4,000 / 10,000 / 25,000 / 60,000** coins; shares weekly facility upgrade cooldown with YA/TG.
- **Resolved Q2 (A):** No career-ending auto-retire in v1; weight-table roll 100 → Major.
- **Resolved Q3 (A):** In-match interactive substitution is Phase 3 (separate PR). Phases 1–2 shipped; Phase 3 plan = [plan-phase3.md](./plan-phase3.md).
- **Resolved injury soft-cap (A+C):** Only starters with fatigue **&lt; 75** roll; at most **one** injury per club per match (first successful eligible roll in starter order).
- Passive fatigue recovery is processed by a scheduled job and/or lazy sync; it does not use the action-energy refill shop.
- No multi-day Hospital build timers in v1 (instant level like YA/TG).
- Existing cosmetic NSS `INJURY` commentary is non-authoritative in Phases 1–2; lasting injuries come from post-match rolls that write card state (FR-015). Phase 3 upgrades mid-match rolls to authoritative (R12).
- Legacy interval match-engine fitness/injury/sub code is reference only; live work targets NSS v2 + BattleCog.
- “Play On” and mid-match pause UI are Phase 3 ([plan-phase3.md](./plan-phase3.md)).
- Bench size target (up to 7 reserves; max 3 subs) is Phase 3.
- Player-facing copy uses **coins**, never dollars.
