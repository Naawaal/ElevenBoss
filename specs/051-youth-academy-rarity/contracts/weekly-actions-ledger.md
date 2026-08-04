# Contract: Academy weekly actions ledger

**Feature**: `051-youth-academy-rarity`  
**Storage**: `academy_weekly_actions` (or equivalent columns) keyed by `(owner_id, UTC week_start)`

## Caps (defaults)

| Action | Cap key | Default |
|--------|---------|---------|
| Promote academy → senior | `academy_weekly_promote_cap` | 2 |
| Paid discovery sign | `academy_weekly_paid_sign_cap` | set in tasks (≥1) |

## Promote RPC additions

1. Lock weekly row; if `promotes_used >= cap` → raise clear error.
2. Senior soft-cap check (existing); on fail prospect stays seated.
3. Optional fee via `apply_club_economy` (`academy_promote_fee`); if `academy_promote_first_free` and `promotes_used = 0`, fee 0 but still increment counter.
4. Atomic: clear `in_academy`, increment counter, return graduation payload fields.
5. Double-tap: second call fails ownership/`in_academy` or hits cap — no duplicate senior card.

## Discovery sign

1. Require `occupied < academy_slot_cap(level)` (strict; over-cap blocked).
2. Increment `paid_signings_used`; reject when at cap.
3. Same integrity generation rules as intake.

## Free intake

Does **not** increment promote/sign counters; only capacity applies.
