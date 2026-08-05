# Phase 0 Research & Technical Decisions: Vote Reminders and Deployment Changelog

## 1. Database State & Atomic Reminder Claim Strategy

### Decision
Store vote reminder state in a dedicated table `public.topgg_vote_reminders` and claim due rows atomically using a stored procedure `claim_due_topgg_vote_reminders(p_limit INTEGER)`.

### Rationale
- Decouples reminder delivery tracking from the core `players` table, keeping player rows lean.
- Prevents concurrent APScheduler workers or multi-instance deployments from delivering duplicate DMs via `FOR UPDATE SKIP LOCKED`.
- `reminder_claimed_at` timestamp allows crashed worker recovery: claims automatically expire after 15 minutes if not completed.

### Alternatives Considered
- *In-memory Python scheduler tracking*: Rejected because bot restarts would lose reminder state and fail to retry blocked/pending DMs.
- *Adding reminder columns directly to `players`*: Rejected because vote reminder state (attempts, fallback statuses, window keys) is auxiliary state that bloats the core user model.

---

## 2. Top.gg Vote Status Re-Verification

### Decision
Before dispatching any reminder DM, the scheduler MUST invoke `check_topgg_vote()` from `apps/discord_bot/core/topgg_vote.py`.

### Rationale
- Guarantees 0% false positive DMs by verifying with Top.gg API that `status == 'not_voted'`.
- Handles users who voted early directly on Top.gg without opening ElevenBoss first.
- Catches Top.gg API rate limits (`429`) or outages (`5xx`/`unavailable`) gracefully by triggering exponential backoff (30m, 60m, 2h) without sending unverified notifications.

### Alternatives Considered
- *Time-based automatic dispatch*: Rejected because if a user already voted outside the bot, they would receive an incorrect "Ready to vote" DM.

---

## 3. Ephemeral Fallback Notice for Disabled DMs

### Decision
When Discord returns `Forbidden` (DMs closed) or transient delivery errors reach retry ceilings, set `fallback_pending = TRUE` and `fallback_created_at = NOW()`. Provide a shared async helper `maybe_send_pending_vote_notice(interaction, db)` to be invoked during `/store` interaction entry points.

### Rationale
- Many Discord users disable DMs from server bots.
- `/store` is the natural high-intent UI path where managers go to claim vote rewards.
- Displaying an ephemeral notice on store entry ensures all voters receive eligibility feedback without spamming or throwing errors.
- Atomic clearing (`fallback_pending = FALSE`, `fallback_shown_at = NOW()`) prevents duplicate fallback popups.

---

## 4. Deployment Changelog Parsing & Deduplication

### Decision
Parse `change_log.md` using regex for heading pattern `## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?`. Deduplicate deployments in database using `game_config` key `last_changelog_deployment` via RPC `claim_deployment_changelog(p_deployment_key TEXT)`.

### Rationale
- Standardizes changelog format using existing `change_log.md` without adding extra files.
- Reads commit SHA from platform environment variables (`GIT_COMMIT_SHA`, `RENDER_GIT_COMMIT`, `RAILWAY_GIT_COMMIT_SHA`).
- Combines `<version>:<commit>` into a deployment key.
- `claim_deployment_changelog` uses PostgreSQL row-level locks on `game_config` to prevent duplicate announcements across multiple bot instances or restarts.

### Alternatives Considered
- *In-memory startup flag*: Rejected because reconnects or secondary worker instances would re-post the changelog embed.
- *Creating a separate `CHANGELOG.md`*: Rejected to comply with project rules (reuse existing `change_log.md`).
