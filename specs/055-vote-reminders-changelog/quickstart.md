# Quickstart & Verification Guide: Feature 055

## Overview
This guide provides runnable instructions to verify Feature 055 (Top.gg Vote Reminders & Deployment Changelog).

---

## 1. Schema Guard Verification

After applying migration `107_vote_reminders_and_changelog.sql`, run `verify_required_schema.sql` or the verification script:

```bash
python scratch/verify_schema_full.py
```

Expected output:
```text
Schema verification passed: topgg_vote_reminders, indexes, and claim RPCs verified.
```

---

## 2. Automated Tests

Run unit and integration tests for vote reminders and deployment changelog:

```bash
pytest tests/test_topgg_vote_reminders.py tests/test_deployment_changelog.py -v
```

Expected output:
```text
tests/test_topgg_vote_reminders.py::test_vote_reminder_window_creation PASSED
tests/test_topgg_vote_reminders.py::test_topgg_reverification_not_voted_sends_dm PASSED
tests/test_topgg_vote_reminders.py::test_dm_forbidden_creates_fallback_notice PASSED
tests/test_topgg_vote_reminders.py::test_store_interaction_clears_fallback_notice PASSED
tests/test_deployment_changelog.py::test_parse_latest_changelog_entry PASSED
tests/test_deployment_changelog.py::test_deployment_claim_deduplication PASSED

================ 6 passed in 1.20s ================
```

---

## 3. End-to-End Verification Steps

### Top.gg Vote Reminder Flow
1. Seed a vote record in `topgg_vote_reminders` with `next_check_at = NOW() - INTERVAL '1 minute'` and `reminder_sent_at = NULL`.
2. Execute task job `python -c "import asyncio; from apps.discord_bot.tasks.topgg_vote_reminder_job import run_topgg_vote_reminders; asyncio.run(run_topgg_vote_reminders(bot))"`.
3. Verify DM delivery or fallback notice creation in `topgg_vote_reminders`.

### Deployment Changelog Announcement Flow
1. Verify `change_log.md` has a valid version section `## [1.4.0] - 2026-08-05`.
2. Start the bot: `python -m apps.discord_bot.main`.
3. Inspect announcement channel for the formatted changelog embed.
4. Restart the bot and verify `last_changelog_deployment` in `game_config` prevents duplicate posting.
