# Feature Specification: 054 — Instant PvP Backfill and Ghost Managers

**Feature Branch**: `054-instant-pvp-backfill`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Feature 054 — Instant PvP Backfill and Ghost Managers. Solves low-population PvP queue failures by introducing a three-level opponent selection system (Live Human -> Ghost Manager -> Calibrated Ranked AI) within a guaranteed 15-second matchmaking window, preserving competitive Ranked play on demand."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instant Ranked Match Search with Ghost Backfill (Priority: P1)

As a competitive manager searching for a Ranked PvP battle during quiet periods or in low-population queues, I want the system to automatically match me with a recent frozen squad snapshot of another real manager (a Ghost Manager) after a short live-human search window, so that I can begin a meaningful Ranked match within 15 seconds without experiencing queue timeouts or endless waiting.

**Why this priority**: Solves the fundamental concurrency problem of low-population PvP queue failures, ensuring 100% on-demand Ranked availability and eliminating manager drop-off.

**Independent Test**: Can be tested by entering the `/battle` Ranked queue when no other manager is queued. After 10 seconds of searching, the system creates a Ranked match against an eligible Ghost Manager snapshot, clearly labeled as a Ghost opponent with reduced Ranked rewards.

**Acceptance Scenarios**:

1. **Given** a manager queue entry with no live human opponents available, **When** search time reaches 10 seconds and an eligible Ghost Manager snapshot exists, **Then** the matchmaker claims the ghost snapshot, starts a single-manager stadium match within 15 seconds total, displays the 👻 GHOST MANAGER badge with snapshot age and rating, and applies Ghost Ranked reward multipliers upon completion.
2. **Given** a manager queued at 9.9 seconds, **When** another live human manager enters the Ranked queue at 10.0 seconds, **Then** an atomic check pairs both live managers together in a 🟢 LIVE MANAGER match with full LP/rewards and rivalry updates, bypassing ghost backfill.
3. **Given** an offline manager whose club is selected as a Ghost opponent, **When** the challenger completes the match, **Then** the ghost owner suffers zero currency loss, zero energy consumption, zero LP changes, zero record changes, and receives zero notifications or mentions.

---

### User Story 2 - Calibrated Ranked AI Fallback (Priority: P2)

As a manager in the Ranked queue when neither a live human nor any eligible Ghost Manager snapshot exists (such as on initial feature rollout), I want the system to construct a division-calibrated Ranked AI opponent so that I can still complete my daily Ranked matches without queue failures.

**Why this priority**: Guarantees system resilience and 100% queue fulfillment even when database snapshot depth is zero or temporary snapshot availability constraints are met.

**Independent Test**: Can be tested by queuing in an environment where `pvp_ghost_snapshots` has no eligible entries. The system transitions from live search to AI backfill and launches a match against a division-calibrated AI opponent.

**Acceptance Scenarios**:

1. **Given** a manager in the Ranked queue with no live humans and zero eligible ghost snapshots, **When** the 10-second threshold expires, **Then** the system launches a Ranked match labeled 🤖 RANKED AI BACKFILL against an AI team calibrated to the manager's division and rating.
2. **Given** a completed Ranked AI Backfill match, **When** final rewards are computed, **Then** the manager receives calibrated Ranked rewards (0.70x coins, 0.75x XP, 0.50x positive LP, 0.25x negative LP), separate daily backfill cap consumption, and no rivalry updates.
3. **Given** AI Practice mode, **When** a manager chooses practice, **Then** it remains a separate zero-LP non-ranked mode (`match_type = 'practice'`), completely distinct from Ranked AI Backfill (`match_type = 'pvp'`).

---

### User Story 3 - Battle Hub Transparency and Daily Backfill Limits (Priority: P3)

As a manager interacting with the `/battle` hub and viewing Match History, I want clear visual indicators during queuing and in match embeds showing the opponent mode (Live, Ghost, or Ranked AI) and clear tracking of my daily backfill allowances, so that I always understand my match context, reward structures, and remaining caps.

**Why this priority**: Preserves competitive integrity and manager trust by ensuring complete transparency regarding opponent types, reward scaling, and daily backfill rules.

**Independent Test**: Can be tested by navigating the `/battle` hub, observing queue status updates at 0s and 5s, viewing opponent-found badges, checking post-match embeds, and observing daily backfill cap enforcement.

**Acceptance Scenarios**:

1. **Given** a manager in the Ranked queue, **When** search progresses past 5 seconds, **Then** the embed updates to show "🔎 Expanding Search" and explains that wider ranges are being checked before selecting a ghost opponent.
2. **Given** a manager who has reached their daily maximum backfill allowance (e.g., 3 ghost/AI backfills in a UTC day), **When** they queue and no live human is found, **Then** the system informs them that daily backfill limits are reached while permitting further search for live human opponents only.
3. **Given** completed matches in Match History, **When** viewed by the manager, **Then** each entry explicitly displays its opponent classification (Live, Ghost, or AI Backfill) alongside exact snapshot age for ghost matches.

---

### Edge Cases

- **Race condition at backfill boundary**: Manager A reaches 10s backfill threshold at the exact millisecond Manager B joins the live queue. An atomic database transaction locks Manager A's entry, performs one final live check, and pairs A and B as a live match if eligible; otherwise, Manager A claims a ghost snapshot and Manager B remains queued for another opponent. Once a ghost match run exists, it is never converted to live mode or cancelled.
- **Cancellation at backfill boundary**: Manager presses cancel at 9.9s while backfill process initiates. Transaction locking ensures either cancellation succeeds (no match created) or match creation commits first (match proceeds and cancel request is cleanly rejected).
- **Stale or blocked ghost snapshot**: Ghost snapshot selected is from a manager who has blocked the searching manager, or whose snapshot is >7 days old. Excluded by strict SQL query filters during candidate selection.
- **Bot restart during queue or ghost match**: If the bot restarts while a manager is queued, `backfill_after` timestamp in Supabase persists, allowing the matchmaker worker to resume processing. If the bot restarts during an active ghost match run, deterministic match state, squad snapshots, and seeds in `match_runs` allow seamless recovery without re-selecting an opponent.
- **Zero ghost snapshots available**: Matchmaker seamlessly falls back to Level 3 (Calibrated Ranked AI), ensuring zero queue failures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Matchmaking MUST implement a 3-level opponent-selection hierarchy: Level 1 Live Human Manager, Level 2 Ghost Manager Snapshot, and Level 3 Calibrated Ranked AI.
- **FR-002**: System MUST transition searching managers to backfill selection (Ghost or AI) within 10 to 15 seconds of queue entry, ensuring 95% of Ranked searches initiate a match in under 15 seconds.
- **FR-003**: Ghost Manager snapshots MUST be frozen, immutable representations of a real manager's starting XI, attributes, formation, tactics, division, and LP captured upon completion of eligible competitive matches or squad updates.
- **FR-004**: Ghost Manager snapshots MUST be eligible only if exactly 11 valid cards are present, snapshot age is 7 days or less, owner is not the searching manager, no mutual blocks exist, and the owner has not exceeded recent encounter cooldowns (24h cooldown per same ghost, max 2 encounters per 7 days).
- **FR-005**: Ghost Manager snapshot selection MUST score eligible candidates based on minimal division difference (±0 initial, up to ±2 max), minimal XI rating difference (±4 initial, up to ±12 max), minimal LP difference (±150 initial, up to ±500 max), snapshot freshness, and candidate usage frequency.
- **FR-006**: When a Ghost Manager match is created, the ghost owner MUST NOT suffer any currency loss, XP loss, LP deduction, energy expenditure, career record change, or receive any Discord notifications/mentions.
- **FR-007**: System MUST classify all Ranked PvP matches using `match_type = 'pvp'` while assigning explicit `opponent_mode` attributes: `'live'`, `'ghost'`, or `'ai_backfill'`.
- **FR-008**: System MUST apply server-enforced reward multipliers based on `opponent_mode`:
  - **Live Human**: 1.00x Coins, 1.00x XP, 1.00x Positive LP, 1.00x Negative LP, Rivalry updates enabled.
  - **Ghost Manager**: 0.85x Coins, 0.90x XP, 0.75x Positive LP, 0.50x Negative LP, Rivalry updates disabled.
  - **Ranked AI Backfill**: 0.70x Coins, 0.75x XP, 0.50x Positive LP, 0.25x Negative LP, Rivalry updates disabled.
- **FR-009**: System MUST enforce daily Ranked match limits and backfill-specific caps (default maximum 3 Ghost/AI backfills per manager per UTC day) within the shared daily Ranked allowance.
- **FR-010**: System MUST restrict manager rivalries, head-to-head records, and rivalry streaks exclusively to `'live'` human matches. Ghost and AI matches MUST NOT alter bilateral manager rivalries.
- **FR-011**: Queue and Stadium interfaces MUST clearly present opponent mode badges (`🟢 LIVE MANAGER`, `👻 GHOST MANAGER`, `🤖 RANKED AI BACKFILL`), snapshot age (for ghost opponents), estimated search progress, and reward implications.
- **FR-012**: System MUST execute live-vs-backfill matchmaking decisions atomically via PostgreSQL RPC transactions to prevent double-run creation or orphaned queue states.
- **FR-013**: System MUST provide a global configuration feature flag (`pvp_backfill_enabled`) allowing instant operational fallback to live-only matchmaking if disabled.

### Key Entities

- **Ghost Snapshot**: Represents a frozen, immutable capture of a real manager's team at a point in time. Attributes include `owner_id`, `club_name`, `global_lp`, `global_division`, `xi_rating`, `snapshot_json` (containing formation, tactics, XI squad cards, card metadata), `snapshot_schema`, `captured_at`, `last_selected_at`, `selection_count`, and `eligible` flag.
- **Ghost Encounter**: Records each instance a manager faces a ghost snapshot or AI backfill for cooldown tracking and daily cap enforcement. Attributes include `run_id`, `challenger_id`, `ghost_owner_id`, `opponent_mode`, `snapshot_captured_at`, and `created_at`.
- **Matchmaking Queue Entry**: Represents an active manager searching for a Ranked match, extended with `backfill_after` timestamp indicating when the entry becomes eligible for Ghost/AI backfill processing.
- **Match Run**: The canonical execution container for a stadium battle, extended with `opponent_mode` (`live`, `ghost`, `ai_backfill`) to dictate finalization logic, presentation, and reward scaling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of Ranked PvP queue entries initiate a match within 15 seconds of pressing Find Opponent.
- **SC-002**: Median match search-to-kickoff latency is 10 seconds or less across all population conditions.
- **SC-003**: 0% of Ghost Manager matches result in passive LP changes, currency deductions, or unwanted Discord mentions for the offline ghost snapshot owner.
- **SC-004**: 0% of Ghost Manager or Ranked AI Backfill matches update official bilateral manager rivalries or head-to-head records.
- **SC-005**: 100% of created matches correctly label opponent mode (Live, Ghost, AI) in pre-match embeds, stadium threads, and Match History.
- **SC-006**: Queue race conditions result in 0 duplicate match runs or corrupted queue states under load testing.
- **SC-007**: AI Practice mode retains 0 LP gains (`match_type = 'practice'`) and remains completely distinct from Ranked AI Backfill.

## Assumptions

- **Existing Stadium Engine Reuse**: The core deterministic match engine, seed generation, commentary rendering, and stadium thread execution will be reused without modifying match outcome calculation rules.
- **Existing Hub Surface**: All interactions will occur within the existing `/battle` hub and slash commands without introducing any new top-level slash commands.
- **Server-Side Config**: All reward multipliers, selection ranges, cooldown windows, and daily caps are server-configured and validated.
- **Ghost Snapshot Population**: Snapshots will be generated automatically upon completion of competitive matches and daily maintenance passes, populating a deep library of real-club opponents.
