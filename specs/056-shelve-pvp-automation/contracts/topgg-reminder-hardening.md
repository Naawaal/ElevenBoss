# Contract: Top.gg Reminder Hardening

**Feature**: `056-shelve-pvp-automation`  
**Keeps**: Feature 055 table/RPC/job surfaces (`107`, `topgg_vote_reminder_job`, `pending_notices`, Store integration)  
**Change**: Behavioral tighten only — no new tables.

## 1. Window completion authority

`reminder_window_key` is authoritative.

A window is **complete** when any of:

- DM sent successfully (`dm_status='sent'`, `reminder_sent_at` set), or
- DM forbidden (`dm_status='forbidden'`, `reminder_sent_at` set, `fallback_pending=true`)

Completed windows MUST NOT be re-claimed for another DM, including across multiple bot instances. `claim_due_topgg_vote_reminders` already filters `reminder_sent_at IS NULL` — Forbidden path MUST set `reminder_sent_at` (or equivalent) so the window exits the due set.

## 2. Scheduling

When upserting eligibility after a vote / store claim:

1. Use Top.gg-provided `next_vote_at` when available.
2. Else `last_vote_at + 12 hours`.
3. Set `next_check_at` to that eligibility time (subject to existing backoff on API failures).

## 3. Job cadence

APScheduler interval: **30 minutes** (`run_topgg_vote_reminders`). Unchanged.

## 4. Fallback

| Event | Effect |
|-------|--------|
| `discord.Forbidden` on DM | Mark window handled + `fallback_pending=true` |
| Transient network / Top.gg errors | Backoff; do not mark sent; never duplicate on later success beyond one notice |
| Store / high-intent open with `fallback_pending` | Show once via `maybe_send_pending_vote_notice`; clear pending |
| User already voted before Store open | Clear stale fallback; no outdated notice |

## 5. RPC

Retain `claim_due_topgg_vote_reminders(p_limit)` from 107 (`FOR UPDATE SKIP LOCKED`, 15-minute stale claim). App-layer completion rules above are mandatory even if SQL is unchanged.

## 6. Test expectations

| Scenario | Outcome |
|----------|---------|
| One expired window, one job run | ≤1 DM |
| Two instances claim same window | ≤1 completed reminder |
| Forbidden DM | 1 Store fallback max; no further DMs for window |
| Top.gg returns next_vote_at | Schedule uses that timestamp |
| Transient failure then success | Still ≤1 notice for window |
