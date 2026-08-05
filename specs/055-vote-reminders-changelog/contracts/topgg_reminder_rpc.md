# Interface Contract: Top.gg Vote Reminder RPC & Python Helpers

## 1. RPC: `claim_due_topgg_vote_reminders`

**Signature**: `public.claim_due_topgg_vote_reminders(p_limit INTEGER)`

**Purpose**: Fetches due vote reminders where `next_check_at <= NOW()` and `reminder_sent_at IS NULL`, setting `reminder_claimed_at = NOW()` using `FOR UPDATE SKIP LOCKED`.

### Input Parameters
| Parameter | Type | Default | Description |
|---|---|---|---|
| `p_limit` | `INTEGER` | `100` | Maximum rows to lock and return in one batch |

### Output Row Structure
```json
{
  "discord_user_id": 976054227459776582,
  "reminder_window_key": "976054227459776582:2026-08-05T12:00:00Z",
  "last_vote_at": "2026-08-05T00:00:00Z",
  "next_vote_at": "2026-08-05T12:00:00Z",
  "next_check_at": "2026-08-05T12:00:00Z",
  "check_failure_count": 0
}
```

---

## 2. Python Helper: `maybe_send_pending_vote_notice`

**Location**: `apps/discord_bot/core/pending_notices.py`

**Signature**: `async def maybe_send_pending_vote_notice(interaction: discord.Interaction, db: Any) -> bool`

### Behavior
1. Checks `topgg_vote_reminders` table for `discord_user_id = interaction.user.id` AND `fallback_pending = TRUE`.
2. If row exists and is current, sends an ephemeral message or followup to `interaction` with the gold vote reminder embed and `[Vote on Top.gg]` button.
3. Atomically sets `fallback_pending = FALSE`, `fallback_shown_at = NOW()`.
4. Returns `True` if notice was sent, `False` otherwise. Does NOT throw exceptions to caller.
