# Feature Specification: League Automation & Config

**Feature Branch**: `021-league-automation-and-config`

**Created**: 2026-07-15

**Status**: Draft (clarifications resolved — ready for `/speckit.plan`)

**Input**: User description: "Fully autonomous APScheduler-driven league lifecycle (registration → seed → season → daily tick → conclusion → loop) with server-owner announce channel/role config via `/admin`, integrating League Dynamics (020: midnight tick, 8/tier divisions, MoMD). Eliminate manual admin season ops as the happy path."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure announce channel & role once (Priority: P1)

A server owner opens `/admin`, sets (or confirms) the league announce channel and mention role, then stops babysitting the league. Automated messages use those two settings for registration opens, schedule posts, daily tick digests, and season conclusions.

**Why this priority**: Without a reliable announce target and ping role, autonomy cannot reach players. The bot already stores these on the existing guild config surface — this story makes them the explicit, required ops for automation (clear labels, validation) rather than inventing a parallel settings store.

**Independent Test**: Owner sets channel + role in `/admin`; an automated registration (or test) post appears in that channel and mentions the role. Missing channel blocks automation with a clear admin-facing reason (no silent no-op).

**Acceptance Scenarios**:

1. **Given** a server owner with admin access, **When** they set the announce channel and mention role in `/admin`, **Then** those values persist and are used for subsequent automated league posts.
2. **Given** automation is enabled but announce channel is unset or inaccessible, **When** the daily automation job runs, **Then** it does not invent a channel; it logs/skips that guild and surfaces a clear failure for admins (e.g. next `/admin` view or ephemeral ops note).
3. **Given** the mention role is unset, **When** automated posts fire, **Then** the post still appears in the announce channel without a role ping (channel-only is acceptable).

---

### User Story 2 - Autonomous season cycle (Priority: P1)

After a Dynamics-style season completes (or when a guild has no active/registration season and automation is on), the system opens a timed registration window, announces it, closes it, seats divisions, starts the season with a schedule post, and later concludes prizes/promo and re-opens registration — without an admin pressing Start/Open each time.

**Why this priority**: This is the core product goal: zero ongoing admin maintenance.

**Independent Test**: On a pilot guild with automation + announce config, complete (or simulate) a season end → within the next job cycle, registration opens with an announce ping; after the window closes with enough managers, a season starts with schedule announcement; no `/admin` Start required.

**Acceptance Scenarios**:

1. **Given** automation enabled, announce channel configured, and no active/registration season, **When** the autonomous job runs, **Then** a registration season opens for a published window (default **48 hours**) and the announce channel is posted: registration open, join via `/league`, and when it closes.
2. **Given** registration is open and the window has ended with sufficient human managers, **When** the job runs, **Then** it seats divisions per League Dynamics rules (exactly **8 clubs/tier**, overflow when humans **> 8**, bot fill), starts an active Dynamics season (**14 matchdays**, midnight UTC windows), and posts the schedule/kickoff to the announce channel (role ping when configured).
3. **Given** Matchday 14 is fully settled, **When** season conclusion runs, **Then** prizes and promotion/relegation apply (Dynamics rules), and the system returns to registration for the next season number without requiring admin action.
4. **Given** a season is still `active` or `registration` under the legacy manual path, **When** automation ships, **Then** that living season is not force-rewritten mid-flight.
5. **Given** automation is enabled for a guild, **When** an admin opens League Management in `/admin`, **Then** they can still **Pause** and **Force End**, but **Open Registration** and **Start Season** are hidden or disabled (the job owns those triggers — no race / duplicate seasons).
6. **Given** a 48h registration window ends with fewer than the minimum humans (`league_min_humans` / existing min), **When** the job evaluates close, **Then** it closes that registration without starting a season, announces that more managers are needed, and opens a **fresh 48h registration only at the next Monday ~00:05 UTC** (aligned with the weekly cycle) — no mid-week extensions or infinite daily stall.

---

### User Story 3 - Daily autonomous tick digest (Priority: P1)

Each UTC day, after the Dynamics hard close (00:00 UTC), the autonomous job (~00:05 UTC) auto-sims expired fixtures, settles MoMD, advances when the matchday is complete, and posts a digest in the announce channel (standings snapshot + MoMD when awarded), pinging the mention role when set. Managers who slept through the deadline see results in the morning.

**Why this priority**: Daily ritual + zero admin pinging is the “living world” experience; builds on 020 Dynamics tick/MoMD rather than replacing formulas.

**Independent Test**: Leave at least one Dynamics fixture unplayed past midnight; after the 00:05 job, fixture is played (`auto_sim`), MoMD rules unchanged (manual-only), announce digest appears with optional role ping; hub shows next matchday unlock / deadline.

**Acceptance Scenarios**:

1. **Given** an active Dynamics season with expired unplayed fixtures, **When** the ~00:05 UTC autonomous tick runs, **Then** those fixtures are auto-simulated first, then matchday settlement (MoMD + advance) proceeds as in League Dynamics.
2. **Given** settlement produces a MoMD award, **When** the digest posts, **Then** the announce channel shows the winner, scoreline, and coin bonus, with role ping when configured; Journal may still receive the existing Dynamics MoMD line without requiring a second conflicting award.
3. **Given** a manager opens `/league` hub during an open matchday, **When** they view the deadline, **Then** they see a clear countdown to **00:00 UTC** for the current matchday.

---

### User Story 4 - Managers only interact via `/league` (Priority: P2)

Managers register and play through existing `/league` hub flows. They are notified by automated pings; they do not need admins to “start matchday” or “advance.” No new player slash commands.

**Why this priority**: Ponytail — automation changes ops side and messaging, not the player command surface.

**Independent Test**: Register during automated registration; play before midnight; miss one night and see auto-sim + digest next day — all via `/league` + announce channel.

**Acceptance Scenarios**:

1. **Given** automated registration is open, **When** a manager uses `/league` hub Register, **Then** they join the registration roster as today.
2. **Given** an automated active season, **When** a manager plays before 00:00 UTC, **Then** the result counts normally (`resolved_by` manual) and is not re-simmed at tick.
3. **Given** automation is on, **When** product surfaces are inventoried, **Then** no new player-facing slash command exists for season lifecycle.

---

### User Story 5 - Safe rollout beside live seasons (Priority: P1)

Automation is feature-flagged. Guilds with in-progress manual/legacy seasons finish under current rules. Pilot guilds enable the flag after announce channel/role are set.

**Why this priority**: Prevents mid-season chaos and matches the 020 grandfathering pattern.

**Independent Test**: Flag off → no autonomous open/start; flag on on a clean guild → lifecycle runs; existing `active` season without automation marker continues until natural/admin end.

**Acceptance Scenarios**:

1. **Given** the automation feature flag is off, **When** the daily job runs, **Then** no guild enters autonomous registration/start solely because of this feature.
2. **Given** an already-active non-automated season, **When** the flag is turned on globally, **Then** that season is left alone until completed (no mid-window rewrite).
3. **Given** a test guild with channel/role set and flag on, **When** ops runs through one full mini-cycle (or shortened registration for test), **Then** registration → start → tick → end → re-registration can be observed without other guilds changing behavior.

---

### Edge Cases

- Announce channel deleted or bot lacks Send Messages / Mention Everyone / role mention permissions mid-season — job skips post; season state transitions still progress when safe; `/admin` shows config broken.
- Mention role deleted — posts without ping.
- Bot downtime across 00:05 — job is **idempotent**: next successful run catches up (auto-sim expired, settle any fully completed matchday once, open registration only if eligible).
- Fewer than 8 humans at seed — **single Seasonal Division**, bot-fill to 8 (Dynamics Q1/Q2). Do not cancel for “not a full human table.”
- Fewer than the minimum human count (`league_min_humans` / existing config default) when the 48h window ends — do not start; announce need for more managers; drop the failed registration season; **re-open a fresh 48h window at next Monday ~00:05 UTC** (not daily retry, not +24h extensions).
- Disbanded / inactive human mid-season — remaining fixtures auto-sim as today when windows expire; no new slash; table stays complete (bot/opponent still get results).
- Registration open while humans still joining — no double season records; one registration season per guild league.
- Automation vs Dynamics flags — autonomous seasons run under Dynamics pacing (14-day, midnight closes, MoMD, tiers). Automation does not reintroduce 28-day rolling windows.
- Dual posting — announce channel is the **pinged public digest**; Journal/MatchDay remain the immersion threads from 020 (do not spam identical long posts thrice).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let server owners set league announce channel and mention role via the existing `/admin` panel (labels may be clarified). Persistence MUST reuse existing guild config fields `league_channel_id` and `announcement_role_id` — **not** a new `guilds` table or duplicate columns.
- **FR-002**: System MUST provide a feature-flagged autonomous league lifecycle job scheduled daily at **~00:05 UTC** that orchestrates registration, start, Dynamics daily tick settlement, season conclusion, and loop — without requiring admin Start for the happy path.
- **FR-003**: Autonomous seasons MUST use League Dynamics rules from 020: 14 matchdays, 00:00 UTC hard close, 8 clubs per division, split when humans > 8, bot fill, MoMD (manual human wins only, configurable coins), top/bottom 2 promo/releg, season prizes per tier.
- **FR-004**: Registration window default MUST be **48 hours** from open (configurable later if needed); open MUST announce in the announce channel with join CTA via `/league` and close timing.
- **FR-005**: Division seating MUST follow Dynamics seating (prefer `league_members.seasonal_division_tier` / prior finish order, fill tier 1 then overflow) — “top 8” means **capacity of Division 1**, not a new skill ladder. `division_tier` already exists on participants from 020; automation MUST assign it at start, not invent a parallel column.
- **FR-006**: Daily tick order MUST be: (1) auto-sim fixtures past `window_end`, (2) settle completed matchday (MoMD + advance or season complete), (3) post announce digest for that guild’s tick outcomes. This MAY consolidate with or wrap the existing Dynamics 00:05 tick job — one coherent schedule, no double-sim races.
- **FR-007**: Season conclusion MUST run prize distribution + promo/releg (existing Dynamics paths), then open the next registration per FR-004 when automation remains enabled.
- **FR-008**: `/league` hub MUST continue to show the current matchday’s 00:00 UTC deadline countdown under Dynamics/autonomous seasons.
- **FR-009**: System MUST NOT add new player-facing slash commands for lifecycle. When automation is enabled for a guild, `/admin` League Management MUST retain **Pause** and **Force End** only; **Open Registration** and **Start Season** MUST be hidden or disabled so the job alone owns those transitions.
- **FR-010**: Automation MUST be disabled by default (feature flag). In-flight seasons without automation ownership MUST be grandfathered.
- **FR-011**: Job steps MUST be idempotent for retries and delayed runs after downtime.
- **FR-012**: Weekly Division Rank (bot-match ladder) MUST remain decoupled from seasonal fixtures.
- **FR-013**: When a registration window closes below the minimum human count, the system MUST NOT start a season and MUST NOT auto-extend mid-week. It MUST announce the shortfall and schedule the next registration open for **Monday ~00:05 UTC** (fresh 48h window).

### Key Entities

- **Guild league config**: Announce channel + mention role (existing guild config fields); automation enablement (flag and/or per-guild opt-in).
- **Season phase**: `registration` → `active` → `completed` (existing statuses); automation may drive transitions without admin clicks.
- **Registration window**: Timed open period before seating/start.
- **Autonomous daily job**: Single ops cadence (~00:05 UTC) covering tick + lifecycle transitions eligible that day.
- **Announce digest**: Role-pinged public summary (registration, schedule, MoMD/standings, season end).
- **Seasonal Division**: Dynamics tier tables (8 clubs); persisted across seasons via promo/releg.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an automated pilot guild, ≥95% of season starts after registration close occur without any admin Start action.
- **SC-002**: Managers receive an announce-channel digest within 20 minutes after 00:00 UTC on tick days when the bot is healthy (MoMD + standings when applicable).
- **SC-003**: After season completion under automation, next registration opens within one daily job cycle (same 00:05 run or the next day’s run if conclusion finished late).
- **SC-004**: Enabling automation does not alter `window_end` or standings of already-active non-automated seasons.
- **SC-005**: Zero new player slash commands; owners configure only channel + role (plus flag/ops enablement).
- **SC-006**: Guilds with 2–8 humans still auto-start a single bot-filled division; guilds with 9+ seed multiple divisions (Dynamics).

## Assumptions

### Codebase alignment (audit vs proposal)

- Announce channel / mention role already live as `guild_config.league_channel_id` and `guild_config.announcement_role_id`, set today from `/admin`. This feature **reuses and clarifies** those — the research ask for a new `guilds.league_announce_channel_id` is rejected as duplicate (Ponytail / Schema Rule).
- `division_tier`, Dynamics tick, MoMD, and promo/releg ship in **020**. This feature **orchestrates and announces** them; it does not re-specify those formulas.
- Season statuses `registration` / `active` / `paused` / `completed` already exist; automation drives transitions rather than inventing a parallel status enum (unless a small `automation` / `config_json` marker is needed to know which seasons the job owns).
- Prefer consolidating 020’s `dynamics_daily_tick_job` into (or sequenced with) the autonomous lifecycle job so only one 00:05 orchestration runs per day.

### Resolved product decisions

- Autonomous seasons always use Dynamics pacing (020).
- Registration length default 48 hours.
- `< 8` humans (but ≥ min) → one division + bots; `> 8` → multi-tier as 020.
- **Under-min at close (Q1=C):** close failed registration; announce; reopen fresh 48h registration at **next Monday ~00:05 UTC** (weekly cycle; no +24h extensions, no daily indefinite stall).
- **Admin when automation on (Q2=A):** Pause + Force End only; hide/disable Open Registration & Start Season.
- MoMD announce digest + existing Journal line allowed; coins awarded once (idempotent).
- Flag default **false**.
- Min human count = existing `league_min_humans` / current registration minimum (do not invent a new threshold in v1).

### Out of scope (v1)

- New public slash commands for registration/start.
- Redesigning Weekly Rank.
- Live match attendance requirements.
- Removing Pause / Force End from `/admin` under automation.
- Creating a separate `guilds` settings table.
- Mid-week registration auto-extensions.

## Dependencies

- League Dynamics (020): midnight windows, seating, MoMD, prizes, promo/releg.
- Existing `/admin` league channel/role setters and `/league` hub.
- APScheduler UTC jobs; guild announce permissions.

## Rollout Strategy *(product)*

1. Ship behind **`league_automation_enabled`** (global and/or per-guild) default off.
2. Grandfather all in-flight seasons.
3. Pilot: set channel + role → enable flag on one guild → watch one registration→tick loop.
4. Expand when digests and start reliability meet SC-001–SC-003.
5. Keep Dynamics flag/behavior consistent — automation assumes Dynamics for new autonomous seasons.
