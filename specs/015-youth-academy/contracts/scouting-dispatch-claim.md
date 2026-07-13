# Contract: Youth Scouting Dispatch & Claim

**Feature**: `015-youth-academy`  
**Economy**: All coin moves via `apply_club_economy`

## Tiers

| `p_tier` | Hours | Cost key | Fog (UI only) |
|----------|-------|----------|---------------|
| `quick` | `scout_hours_quick` (2) | `scout_cost_quick` (3000) | stars + position |
| `standard` | 8 | 10000 | + OVR |
| `deep` | 24 | 25000 | + OVR + POT/stars |

## `dispatch_youth_scout(p_owner_id bigint, p_tier text) → jsonb`

### Preconditions

- Valid tier.
- `scouting_finishes_at` is null or ≤ now().
- No claimable unsigned report with `expires_at > now()` (force resolve/expire first).
- Sufficient coins.

### Effects

- `apply_club_economy` debit with reason `youth_scout_<tier>`, idempotency key `scout:{owner}:{tier}:{finishes_at_iso}` or similar unique.
- Set `players.scouting_finishes_at = now() + hours`.

### Returns

```json
{ "tier": "standard", "finishes_at": "…", "cost": 10000, "coins_remaining": … }
```

---

## `finalize_youth_scout_report(p_owner_id bigint, p_prospects jsonb, p_tier text default null) → jsonb`

Called by bot when `now >= scouting_finishes_at` and no open report:

- Insert `scouting_reports` with 3 prospects (generated in app via same academy-tier generator), `expires_at = now + ttl`.
- Tier from `p_tier` or `players.scouting_active_tier`.
- Clear `scouting_finishes_at` and `scouting_active_tier`.

---

## `sign_youth_scout_prospect(p_owner_id bigint, p_report_id uuid, p_index int) → jsonb`

### Preconditions

- Report owned, not expired, `signed_card_id` null.
- `p_index` in 0..2.
- Free academy slot ≥ 1.

### Effects

- Insert `player_cards` from `prospects_json[p_index]` with `in_academy = TRUE` (same fields as intake).
- Set `signed_card_id`.
- Max **one** sign per report.

### Errors

- `Academy slots full`
- `Report expired or already signed`

---

## Idempotency / double-tap

- Dispatch: unique ledger idempotency prevents double charge.
- Sign: `signed_card_id` guard.
