# Quickstart: Autonomous League Administration Policy

**Feature**: `027-league-autonomous-admin`  
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Validate Discord authority removal, League Time defaults/freeze, and operator recovery without relying on admin babysitting.

## Prerequisites

- Migration `070` applied (and `072` if shipped for default-hour alignment)
- `supabase/scripts/verify_required_schema.sql` passes
- Bot can reach Supabase; operator host has the same DB credentials for the recover script
- A pilot guild with Lifecycle V1 effective (via `game_config` / DB — **not** Discord cutover UI)

## 1. Admin surface inventory

1. Run `/admin` as bot owner → select pilot guild.
2. Confirm hub shows **Announcements**, **Server Settings** (→ **League Time**), and **Switch Server**.
3. Confirm **League Management** is gone.
4. Open League Time → only timezone + resolution hour + preview.
5. Automated check: `tests/test_admin_surface_inventory.py` (or equivalent grep) asserts banned `league_admin_*` lifecycle custom_ids are absent.

**Expected**: SC-002 — exactly one league schedule config surface; zero lifecycle mutators.

## 2. League Time validation + preview

1. Enter invalid TZ `UTC+5:45` → rejected.
2. Enter unknown `Not/AZone` → rejected.
3. Enter `Asia/Kathmandu` + `20:00` (or hour `20`) → saved; preview shows local wording, UTC equivalent, “applies from the next season.”

**Expected**: FR-006–FR-008; SC-005.

## 3. Defaults non-blocking

1. On a guild with NULL `league_timezone` / `league_resolution_hour_local`, do not save League Time.
2. Trigger preparation (engine wake or operator recover after registration lock with enough humans).
3. Confirm season freeze uses `UTC` + hour `0` and matchday windows exist.

**Expected**: FR-012/FR-013; SC-004. Preparation does not error with “requires league_timezone”.

## 4. Future-only application

1. With an **active** V1 season and published matchday windows, note a fixture `window_end`.
2. Change League Time to a different zone/hour.
3. Re-read the same fixture/season snapshot columns.

**Expected**: SC-003 — active deadlines unchanged; new settings used only on the **next** season’s prepare.

## 5. Autonomous cycle (no Discord lifecycle)

1. Do not use any admin start/open/pause/end controls (they must not exist).
2. Let scheduler wake (or operator recover) advance registration → prepare → matchdays as due.
3. Confirm `/league hub` can register only while registration is open; no hub control opens registration early.

**Expected**: SC-001 / SC-008.

## 6. Operator recovery

1. Simulate a stalled/failed retryable operation or stop the bot across a deadline.
2. Ensure `.env` has `DATABASE_URL` or `SUPABASE_URL` + `SUPABASE_KEY`, then run:
   `python scripts/league_lifecycle_recover.py` (optionally `--guild-id <id>`).
3. Confirm catch-up settles due work once; re-run is safe (idempotent ops).
4. Re-run the script repeatedly against the same “now” → no duplicate prizes/promo/fixture results (SC-007).

**Expected**: FR-016–FR-018; SC-006/SC-007. No Discord admin button required.

## 7. Doc reconciliation

- [x] `026` `contracts/admin-and-hub-surfaces.md` amended to match this feature’s Discord contract
- [x] `change_log.md` notes League Time–only admin + autonomous operation on ship

**Quickstart walkthrough note (T036):** Automated unit/inventory tests green (24 passed). Full Discord pilot scenarios 1–5 require a live bot session — validate on deploy. Operator script syntax/import path ready (`scripts/league_lifecycle_recover.py`).

## Related contracts

- [discord-admin-surfaces.md](./contracts/discord-admin-surfaces.md)
- [league-time-settings.md](./contracts/league-time-settings.md)
- [operator-recovery.md](./contracts/operator-recovery.md)
- [data-model.md](./data-model.md)
