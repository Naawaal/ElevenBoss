# Feature Specification: Vote Reminders and Deployment Changelog

**Feature Branch**: `055-vote-reminders-changelog`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Feature 055 — Vote Reminders and Deployment Changelog. Scope: Two lightweight quality-of-life automations (Top.gg vote reminders and deployment changelog announcement). Top-level slash commands: None. Scheduler: Existing APScheduler instance. Primary integrations: core/topgg_vote.py, existing interaction handlers, startup lifecycle, change_log.md. Ponytail approach: One small reminder-state table, one startup service, and shared helper functions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Top.gg Vote Eligibility DM Reminder (Priority: P1)

As a manager who votes for ElevenBoss on Top.gg, I want to receive a single gentle direct message when my 12-hour voting cooldown has elapsed so that I can cast another vote and earn rewards without having to manually track the clock.

**Why this priority**: Top.gg votes drive server discovery and manager growth. Automating eligibility notifications increases voting frequency and player retention without requiring manual user checking.

**Independent Test**: Can be tested by seeding a vote reminder record with `next_check_at <= NOW()`, triggering the scheduler job, verifying Top.gg status returns `not_voted`, and confirming a single gold-styled DM with a [Vote on Top.gg] button is delivered.

**Acceptance Scenarios**:

1. **Given** a manager voted 12 hours ago and their cooldown has expired, **When** the 30-minute vote reminder scheduler job runs and Top.gg API confirms `not_voted`, **Then** the bot sends a single non-intrusive DM with a [Vote on Top.gg] button and marks `reminder_sent_at` to prevent duplicate DMs for that vote window.
2. **Given** a manager's vote cooldown has expired but Top.gg API returns `voted` (user already voted again), **When** the scheduler job runs, **Then** no DM is sent, the new vote window is saved, and `next_check_at` is updated to the new eligibility timestamp.
3. **Given** Top.gg API returns HTTP 429 (rate limit) or 5xx error, **When** the scheduler job runs, **Then** no DM is sent, the check failure count increases, exponential backoff (30m/60m/2h) is applied to `next_check_at`, and the job does not interpret API failure as vote eligibility.

---

### User Story 2 - Ephemeral Fallback Notice for Disabled DMs (Priority: P2)

As a manager with DMs disabled or blocked, I want to see an ephemeral notification when I open `/store` or high-intent surfaces after my vote cooldown expires so that I don't miss out on voting rewards even if DMs fail.

**Why this priority**: Many Discord users disable DMs from server bots. Providing a graceful fallback in high-intent UI paths ensures all voting managers receive notice without breaking command flow.

**Independent Test**: Can be tested by simulating a DM delivery failure (`Forbidden`), verifying `fallback_pending = TRUE` is recorded in `topgg_vote_reminders`, running `/store`, and verifying an ephemeral notice with a [Vote on Top.gg] button is appended to the store response.

**Acceptance Scenarios**:

1. **Given** a manager whose vote reminder DM failed with `Forbidden` (`fallback_pending = TRUE`), **When** the manager opens `/store` or `/battle`, **Then** the bot displays an ephemeral notice explaining that voting is ready and clears `fallback_pending`.
2. **Given** a manager with `fallback_pending = TRUE` who votes again before opening `/store`, **When** the manager opens `/store`, **Then** the fallback notice check sees the user has already voted, clears the stale fallback, and does not show an outdated notice.

---

### User Story 3 - Automated Deployment Changelog Announcement (Priority: P3)

As a manager in a Discord server, I want to see a formatted changelog announcement in the server channel whenever a new version of ElevenBoss is deployed so that I stay informed about new features and bug fixes.

**Why this priority**: Player transparency and engagement increase when updates are highlighted immediately upon deployment. Automating changelog posting eliminates manual administrative release posts.

**Independent Test**: Can be tested by deploying a new release commit with updated `change_log.md` entries, triggering the bot startup sequence, and verifying a single formatted changelog embed is posted to the target announcement channel and deduplicated in `game_config`.

**Acceptance Scenarios**:

1. **Given** a new deployment with version `1.4.0` in `change_log.md` and commit `ea590ab`, **When** the bot completes startup synchronization, **Then** it parses the latest release section from `change_log.md`, builds a formatted embed with Added/Fixed sections, posts to the primary announcement channel, and records `last_changelog_deployment` in `game_config`.
2. **Given** the bot restarts after a disconnect or crash without a new code deployment, **When** startup completes, **Then** the deployment key matches `last_changelog_deployment` in `game_config` and no duplicate changelog is posted.
3. **Given** multiple bot instances start simultaneously, **When** checking deployment status, **Then** atomic database locking (`claim_deployment_changelog`) ensures exactly one instance posts the changelog.

---

### Edge Cases

- What happens when a user votes multiple times in rapid succession or triggers duplicate webhooks? The `reminder_window_key` and upsert logic enforce `EXCLUDED.next_vote_at >= topgg_vote_reminders.next_vote_at`, ensuring older webhooks cannot overwrite newer vote windows.
- What happens when the bot crashes while dispatching a batch of 100 reminders? The database claim `reminder_claimed_at` expires after 15 minutes, allowing a subsequent scheduler run to reclaim and process unfulfilled rows safely.
- What happens when `change_log.md` is missing, malformed, or has no valid version header? The changelog parser logs a warning and cleanly skips posting without throwing exceptions or blocking bot startup.
- What happens when no announcement channel or fallback text channel is messageable? The changelog service logs the condition and skips posting without updating `last_changelog_deployment`, allowing retry on a future restart after permissions are fixed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST record vote eligibility in a dedicated `topgg_vote_reminders` database table whenever a user votes via Top.gg webhook or claims a store vote reward.
- **FR-002**: System MUST deduplicate vote reminders per vote window using a unique `reminder_window_key` (`<discord_user_id>:<next_vote_at>`).
- **FR-003**: System MUST execute a 30-minute APScheduler job (`topgg_vote_reminder_job`) that fetches due reminders (`next_check_at <= NOW()`) in bounded batches (`LIMIT 100 FOR UPDATE SKIP LOCKED`).
- **FR-004**: System MUST verify current Top.gg vote status via `check_topgg_vote()` before sending any reminder DM and MUST NEVER assume eligibility based on time alone.
- **FR-005**: System MUST send exactly one gold-styled DM with a [Vote on Top.gg] button when Top.gg returns `not_voted` and update `reminder_sent_at` and `dm_status = 'sent'`.
- **FR-006**: System MUST handle API errors (`status == 'unavailable'`) or rate limits (`429`) by deferring execution using exponential backoff (30m, 60m, 2h) without sending DMs.
- **FR-007**: System MUST record `fallback_pending = TRUE` when DM delivery fails with `Forbidden` or transient HTTP errors exceeding retry ceilings.
- **FR-008**: System MUST provide a shared helper `maybe_send_pending_vote_notice()` invoked during high-intent interaction flows (such as `/store`) that displays an ephemeral vote reminder notice if `fallback_pending = TRUE`.
- **FR-009**: System MUST clear pending fallbacks and update the eligibility window if a user votes before seeing the fallback notice.
- **FR-010**: System MUST parse the latest version section from `change_log.md` on bot startup using `deployment_changelog.py`.
- **FR-011**: System MUST generate a deployment key (`<version>:<commit>`) using environment commit variables (`GIT_COMMIT_SHA`, `RENDER_GIT_COMMIT`, etc.).
- **FR-012**: System MUST deduplicate deployment announcements via atomic database locking (`claim_deployment_changelog` / `last_changelog_deployment` in `game_config`) to ensure exactly one announcement per release across restarts and multi-instance deploys.
- **FR-013**: System MUST resolve target announcement channels in priority order: (1) Configured league announcement channel, (2) `CHANGELOG_CHANNEL_ID` environment variable, (3) First writable non-thread text channel.
- **FR-014**: System MUST format changelog announcements into a clean Discord embed featuring version, date, short commit hash, and categorized bullet points (Added, Changed, Fixed, Removed) capped at Discord embed size constraints.
- **FR-015**: System MUST NOT introduce any new top-level slash commands or alter existing player progression formulas.

### Key Entities

- **Vote Reminder (`topgg_vote_reminders`)**: Represents a voter's reminder state for the active vote window. Key attributes: `discord_user_id` (PK), `last_vote_at`, `next_vote_at`, `reminder_window_key`, `reminder_claimed_at`, `reminder_sent_at`, `dm_status`, `fallback_pending`, `next_check_at`, `check_failure_count`.
- **Deployment Changelog Record (`game_config` -> `last_changelog_deployment`)**: Tracks posted deployment metadata. Key attributes: `version`, `commit`, `posted_at`, `channel_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of eligible vote reminders undergo Top.gg API re-verification before DM dispatch, resulting in 0% false-positive DMs sent to users who have already voted.
- **SC-002**: 100% of failed DM deliveries (`Forbidden`) generate an ephemeral fallback notice accessible on the user's next `/store` interaction.
- **SC-003**: 100% of bot restarts and multi-instance deployments deliver at most 1 changelog announcement per code commit.
- **SC-004**: Vote reminder scheduler batch processing completes in under 5 seconds for a batch size of 100 rows.

## Assumptions

- Top.gg API key (`TOPGG_TOKEN`) and Bot ID (`TOPGG_BOT_ID`) are configured in `.env` for production verification.
- `change_log.md` follows standard Keep a Changelog markdown format (`## [X.Y.Z] - YYYY-MM-DD`).
- APScheduler is initialized and running in `main.py`.
- No new top-level slash commands are required; functionality integrates into existing hubs (`/store`) and background schedulers.
