# Contract: `process_youth_intake` seating

**Feature**: `015-youth-academy`  
**Replaces**: body of `public.process_youth_intake(bigint, jsonb)` from 042 (+ facility-aware callers)

## Behavior

1. Idempotent per `(owner_id, current_intake_week)` via `youth_intake_log` — unchanged.
2. Read `youth_academy_level`; compute `cap = academy_slot_cap(level)`; `used = COUNT` academy cards; `free = max(0, cap - used)`.
3. Take first `free` cards from `p_cards` (preserve order); insert into `player_cards` with:
   - `in_academy = TRUE`
   - `academy_progress = 0`
   - `academy_seated_at = NOW()`
   - same stat/POT fields as today
4. Do **not** insert skipped cards; do **not** delete existing academy rows.
5. Log `card_ids` = seated only.
6. Return JSON:

```json
{
  "owner_id": 123,
  "intake_week": "2026-07-07",
  "card_ids": ["…"],
  "seated": 2,
  "skipped": 1,
  "slots_used": 4,
  "slots_cap": 4,
  "already_processed": false
}
```

## Caller

`apps/discord_bot/tasks/youth_intake_notifier.py` — generate full batch as today; RPC applies seating; DM/embed should mention skipped if `skipped > 0` and point to Manage Academy.

## Errors

- Manager not found / empty payload — same as today.
- Payload longer than config max — same as today (trim or raise); seating still limited by `free`.
