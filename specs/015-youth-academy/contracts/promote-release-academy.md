# Contract: Promote & Release Academy Players

**Feature**: `015-youth-academy`

## `promote_academy_player(p_owner_id bigint, p_card_id uuid) → jsonb`

### Preconditions

- Card exists, `owner_id` matches, `in_academy = TRUE`, not retired.
- Senior count (`NOT in_academy AND NOT is_retired`) &lt; `senior_roster_cap`.

### Effects

- `in_academy = FALSE`
- `academy_progress = 0`
- `academy_seated_at = NULL` (or keep for analytics — v1 null OK)
- Remains unassigned to XI (no auto `squad_assignments` insert)

### Returns

```json
{ "card_id": "…", "overall": 66, "potential": 84, "early_promote": true }
```

`early_promote` true when `overall < academy_ready_ovr`.

### Errors

- `Not an academy player`
- `Senior roster is full (N/CAP). Sell or release a senior player first.`

---

## `release_academy_player(p_owner_id bigint, p_card_id uuid) → jsonb`

### Preconditions

- Card exists, owner matches, `in_academy = TRUE`.

### Effects

- Delete `squad_assignments` for card if any (defensive).
- `DELETE` from `player_cards`.

### Returns

```json
{ "released_card_id": "…", "name": "…" }
```

### Errors

- `Not an academy player`

---

## Age-out (inside `process_daily_academy_growth`)

For each academy card with age ≥ `academy_age_out`:

1. Attempt same promote logic.
2. On failure → delete + append to job result `age_out_released[]` for notifier.
