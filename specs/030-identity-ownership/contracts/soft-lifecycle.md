# Contract: Soft Lifecycle

**Feature**: US-42.1 | **FR-014…015**

**Note (US-42.1)**: Soft `inactive` / `abandoned` labels never free the Discord id for a second club — `register_new_player` still hits EXISTS / PK → `ALREADY_REGISTERED`.

## States

| Status | Meaning |
|--------|---------|
| `active` | Normal human club |
| `inactive` | ≥30 UTC days since `last_qualifying_activity_at` |
| `abandoned` | ≥90 UTC days since activity |

AI clubs (`is_ai = true`): classify skips or no-ops.

## RPCs

### `touch_club_activity(p_club_id BIGINT)`

- Updates `last_qualifying_activity_at = NOW()`.
- If status in (`inactive`, `abandoned`), set `identity_status = 'active'` and bump `identity_status_changed_at` (auto-wake on real play — matches “same club recovers”).
- No-op / raise if club missing.
- Does not grant coins/XP.

### `classify_club_identity_status(p_club_id BIGINT DEFAULT NULL)`

- If `p_club_id` null: optional batch humans only (implementation may start single-id only for MVP).
- Compute age of `last_qualifying_activity_at` vs NOW() at UTC.
- Set `abandoned` if ≥90d, else `inactive` if ≥30d, else `active`.
- Do not delete rows.
- Return JSON `{discord_id, old_status, new_status, ...}`.

### `recover_club_identity(p_club_id BIGINT)`

- Sets `active`, touches activity timestamp.
- App layer must verify caller owns `p_club_id` before invoke (or RPC accepts only matching id from trusted bot).

## Thresholds

Defaults 30 / 90 in package `identity.py` and/or `game_config` keys:

- `identity_inactive_days` = 30  
- `identity_abandoned_days` = 90  

US-42.3 may change numbers; must not introduce hard delete.

## Non-goals

- Auto-relegate / kick from league seats (42.3/42.5).
- Manager-facing `/abandon` command.
