# Feature Specification: Match Live Immersion Fixes

**Feature Branch**: `004-match-live-immersion`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Fix three immersion-breaking live-match flaws without changing core Markov chain math: (1) Ghost Match — early goals vanish from the 5-line ticker; add a persistent Goal Scroll under the scoreboard plus a half-time ticker marker. (2) Generic Bot Names — replace 'Opponent Striker/Midfielder' with real generated bot player names in event actors. (3) 0%–100% possession / 0 shots snowball — enforce a minimum transition probability floor so the trailing team can still win midfield rolls and generate highlights."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Persistent Goal Scroll (Priority: P1)

As a manager watching a live match, I can always see every goal scored so far—even if I look away while the rolling commentary ticker advances—so a lopsided score never feels like it appeared out of nowhere.

**Why this priority**: The “ghost match” effect is the most immersion-breaking failure: the scoreboard says `0–4` while the ticker only shows late events. Managers lose the narrative of how the match slipped away.

**Independent Test**: Run a live match that produces at least three goals across different minutes (including before the 60th minute). Confirm each goal remains listed in a Goal Scroll under the scoreboard while the commentary ticker continues to roll.

**Acceptance Scenarios**:

1. **Given** a live match is in progress, **When** a goal is scored, **Then** a new Goal Scroll line appears under the scoreboard showing minute and scorer (e.g. `⚽ 14' Player Name`), and the scoreboard updates as today.
2. **Given** more than five commentary events have occurred since kickoff, **When** the manager views the live embed, **Then** early goals remain visible in the Goal Scroll even if they have scrolled out of the commentary ticker.
3. **Given** ten or fewer goals have been scored, **When** the live embed refreshes, **Then** all goals appear in the Goal Scroll in chronological order.
4. **Given** more than ten goals have been scored, **When** the live embed refreshes, **Then** the Goal Scroll shows at most the most recent ten goals (oldest drop off) and does not break Discord embed limits.
5. **Given** no goals have been scored yet, **When** the live embed is shown, **Then** the Goal Scroll area is empty or omitted cleanly (no placeholder clutter).

---

### User Story 2 - Half-Time Marker in the Ticker (Priority: P1)

As a manager watching a live match, I see a clear half-time break in the commentary ticker when the match reaches the midpoint, so the flow of the game is readable even when I only glance at recent lines.

**Why this priority**: Without a half-time cue, the ticker feels like one continuous blur; managers cannot tell whether they are watching first-half or second-half action.

**Independent Test**: Watch a live match through the 45th minute; confirm a distinct half-time separator appears in the commentary ticker (e.g. `--- HALF TIME ---` or equivalent clear marker).

**Acceptance Scenarios**:

1. **Given** a live match reaches half-time (~45'), **When** the live embed updates, **Then** the commentary ticker includes a clear half-time separator line.
2. **Given** the half-time marker has appeared, **When** later second-half events roll into the ticker, **Then** the marker remains visible until it naturally scrolls out of the last-N ticker window (same retention rules as other ticker lines).
3. **Given** a match that never reaches half-time (aborted / error path), **When** the live flow ends early, **Then** no spurious half-time marker is invented after the fact.

---

### User Story 3 - Real Bot Player Names (Priority: P1)

As a manager playing against a bot club, I see named opponents in commentary and goal lines—not generic labels like “Opponent Striker”—so the match feels like a contest against a real squad.

**Why this priority**: Positional placeholder names break the fourth wall immediately and make every bot match feel unfinished.

**Independent Test**: Start a bot match; confirm kickoff/chance/goal/miss commentary and Goal Scroll lines use distinct generated player names for the bot side, never the literal strings “Opponent Striker” or “Opponent Midfielder” (or equivalent positional stubs).

**Acceptance Scenarios**:

1. **Given** a bot opponent squad is generated for a live match, **When** a bot player participates in an attack or scoring event, **Then** the event’s actor is that player’s display name from the bot squad roster.
2. **Given** multiple bot goals in one match, **When** Goal Scroll and ticker lines are shown, **Then** scorers are named individuals (may repeat if the same player scores twice), not role labels.
3. **Given** a human-vs-human (friendly) match, **When** events fire, **Then** existing real card names continue to appear (no regression to stubs).
4. **Given** a bot match post-match summary or MOTM-style copy that references a player, **When** shown, **Then** it uses a real squad name when a player is available (no new “Opponent …” stubs introduced by this work).

---

### User Story 4 - No Total Possession Snowball (Priority: P2)

As a manager whose team is outmatched or trailing, I still see my side win midfield battles and create occasional chances—so post-match possession and shots never collapse to a lifeless `0% / 0 shots` when my attack rating was non-trivial.

**Why this priority**: A 0–100 possession line with zero shots destroys trust in the sim even when the scoreline is believable. Secondary to live UX fixes because it is a fairness/feel tweak, not a missing UI surface.

**Independent Test**: Simulate (or play) matches where one side is clearly weaker but not zero-rated; confirm the weaker side’s possession is never exactly 0% across a full match, and that they record at least some midfield/attack highlights over a batch of runs.

**Acceptance Scenarios**:

1. **Given** both teams have usable squads (non-empty starting XI), **When** a full match completes, **Then** neither side’s possession is reported as exactly 0% (and the other as 100%) as a normal outcome.
2. **Given** a team is losing and has negative momentum, **When** midfield/build-up transition rolls occur, **Then** that team still has a meaningful minimum chance (at least ~5%) to win the roll and progress play.
3. **Given** a weaker attack vs stronger defense (e.g. ~78 ATT vs ~84 DEF), **When** a full match completes, **Then** the weaker side typically records some shots or attacking highlights across the match—not a guaranteed zero-shot blank every time.
4. **Given** a clearly superior side, **When** matches are simulated in bulk, **Then** favorites still win more often and dominate possession on average—the floor softens snowballs; it does not force 50–50 games.

---

### Edge Cases

- What happens when more than 10 goals are scored? Goal Scroll keeps the newest 10; older goals remain reflected only in the scoreboard total.
- What if the same player scores multiple times? Each goal gets its own Goal Scroll line with the same name and distinct minutes.
- What if a goal event lacks a usable actor name? Fall back to a club-side label (home/away club name or “Unknown”)—never invent “Opponent Striker”-style positional stubs.
- What if half-time and a goal occur in the same update window? Both appear; order preserves match chronology (goal before or after the break according to sim minute).
- What if the manager only opens the final post-match embed? Goal Scroll is a live-embed concern; post-match box score remains the source of truth for final stats (possession/shots), which must reflect the floored transition behavior.
- What if a match is abandoned mid-stream? Partial Goal Scroll and ticker state are acceptable; no requirement to invent missing early goals after the fact.
- Own goals / rare event types: if the product already has special goal attribution, preserve it; otherwise attribute to the scoring side’s named player when available.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Live match embeds MUST show a persistent Goal Scroll directly beneath the scoreboard listing goals scored so far (minute + scorer), independent of the rolling commentary ticker.
- **FR-002**: Goal Scroll MUST retain up to 10 goal lines; when capacity is exceeded, the oldest Goal Scroll lines drop first.
- **FR-003**: Live match embed layout MUST present, in order: Scoreboard → Goal Scroll → Momentum Bar → Commentary Ticker (last ~5 events), preserving existing momentum and ticker behavior except as specified here.
- **FR-004**: When the match reaches half-time, the commentary ticker MUST include a clear half-time separator (e.g. `--- HALF TIME ---`).
- **FR-005**: Commentary ticker MUST continue to show approximately the last 5 events; Goal Scroll MUST NOT replace the ticker—both coexist.
- **FR-006**: Bot opponent event actors (attack, scoring opportunity, goals, misses, and Goal Scroll scorers) MUST use generated roster player display names, not generic positional labels such as “Opponent Striker” or “Opponent Midfielder”.
- **FR-007**: Human-owned card names in live events MUST continue to resolve as they do today (no regression).
- **FR-008**: Match phase transition rolls MUST enforce a minimum success probability floor of approximately 5% for contested transitions (including midfield → build-up style progress), even under heavy rating/momentum disadvantage.
- **FR-009**: The probability floor MUST NOT rewrite core Markov state structure or remove existing momentum/stagnation mechanics; it only clamps extreme near-zero transition chances.
- **FR-010**: Post-match possession and shot tallies MUST be derived from the same live simulation that applied the floor (no separate “pretty stats” rewrite that disagrees with what the manager watched).
- **FR-011**: These immersion fixes MUST apply to all live-streamed match presentations that use the standard live scoreboard + ticker pattern (bot matches and other modes sharing that live UI).
- **FR-012**: No new slash commands, hubs, or database tables are introduced by this feature.

### Key Entities

- **Live Match Embed**: The updating Discord message managers watch during a match; composed of scoreboard, Goal Scroll, momentum, and ticker.
- **Goal Scroll Entry**: A durable goal line (minute, scorer name, optional side cue) retained for the life of the live embed (capped).
- **Commentary Ticker Event**: A short-lived narrative line (last ~5), including half-time separator and play-by-play.
- **Bot Roster Player**: A generated opponent squad member with a display name used whenever that player is the event actor.
- **Transition Probability Floor**: The minimum chance a disadvantaged side still has to win a contested phase transition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In live matches with 3+ goals where at least one goal occurs before the 60th minute, managers who only look at the live embed after the 60th minute can still identify every goal’s minute and scorer from the Goal Scroll without scrolling chat history.
- **SC-002**: 100% of sampled bot-match goal and attack commentary lines use non-generic player names (zero occurrences of “Opponent Striker”, “Opponent Midfielder”, or equivalent positional stubs in actor fields).
- **SC-003**: Across a batch of ≥20 full simulations with both sides fielding valid XIs, 0% of matches report exact 0–100 possession splits.
- **SC-004**: Across the same batch, the weaker side’s mean possession sits in a believable competitive band (illustratively ~25–45% when clearly outmatched), not stuck at 0%.
- **SC-005**: Favorites still win a clear majority of heavily mismatched matches (floor does not flatten competitive outcomes into coin-flips).
- **SC-006**: Managers can identify half-time from the live ticker alone in every completed live match that reaches the midpoint.

## Assumptions

- Architecture stays as today: pure simulation → stateless commentary hydration → Discord live UI manager. This feature does not merge those layers.
- Core Markov chain structure and rating-driven odds remain; only a minimum transition probability clamp and event-actor naming / live-embed presentation change.
- Goal Scroll cap of 10 and ticker window of ~5 match the product request; exact emoji/copy may follow existing match icon conventions.
- Half-time is the standard midpoint (~45'); extra-time / penalties live presentation is out of scope unless already present.
- Bot squad generation already (or will) produce named players for a starting XI; the immersion requirement is that those names reach live event actors and Goal Scroll lines.
- “Opponent Striker / Midfielder” stubs currently appear because bot cards or event actors are filled with positional placeholders; fixing naming at the source of bot roster / event payload is in scope, inventing a new naming service is not required if generation already exists elsewhere.
- Scope is live-match immersion and related post-match stats consistency—not a full commentary rewrite, not injury/sub UX, and not economy/XP changes.
- No schema/migration work is expected for this feature.
- League and friendly live UIs that share the standard live pattern inherit the same Goal Scroll / naming / floor behavior; one-off legacy paths should be updated or explicitly left documented if truly unused.
