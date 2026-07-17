# Contract: Expire Stale Transfer Listings

**Feature**: `017-player-transfer-market`

## `expire_stale_transfer_listings() → jsonb`

### Trigger

APScheduler hourly job (or similar cadence) via `apps/discord_bot/tasks/transfer_listing_expiry_job.py`.

### Effects

Set-based:

```text
UPDATE transfer_listings
SET status = 'expired', cancelled_at = now()
WHERE status = 'active' AND expires_at <= now()
```

No coin movement. Cards become available to former sellers.

### Returns

```json
{ "expired_count": 3 }
```

### Notes

- Purchase path should also refuse `expires_at <= now()` even if sweeper lag.
- Optional: cancel RPC shared internal helper for status transition.
