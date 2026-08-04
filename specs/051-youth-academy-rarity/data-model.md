# Data Model: Youth Academy Rarity-Cap Redesign

**Feature**: `051-youth-academy-rarity`  
**Date**: 2026-08-04  
**Depends on**: Feature 015 seating (`in_academy`), Feature 049 `rarity_potential_cap` / integrity asserts.

---

## Entities

### Academy Prospect (`player_cards` row with `in_academy = TRUE`)

| Field | Type | Notes |
|-------|------|--------|
| *(existing)* `id`, `owner_id`, `rarity`, `overall`, `potential`, attrs, `age`, … | | Same card lifecycle as senior |
| *(existing)* `in_academy` | boolean | Holding seat |
| *(existing)* `academy_progress` | int | 0–99 toward OVR tick |
| *(existing)* `academy_seated_at` | timestamptz | Seated timestamp |
| **NEW** `pot_visible_lo` | int | Inclusive visible lower bound |
| **NEW** `pot_visible_hi` | int | Inclusive visible upper bound |
| **NEW** `scout_assessment_level` | text/int | e.g. `none` / `quick` / `standard` / `deep` or 0–3 |
| **NEW** `academy_origin` | text | `weekly_intake` \| `paid_scout` \| `migration` \| `admin` |
| **NEW** `academy_age_out_pending_at` | timestamptz null | Grace start |
| **NEW** `academy_warned_aging_at` | timestamptz null | Optional first-warn marker |

**Invariants**:
- `overall ≤ potential ≤ rarity_potential_cap(rarity)`
- While `in_academy`: `pot_visible_lo ≤ potential ≤ pot_visible_hi`
- `1 ≤ pot_visible_lo ≤ pot_visible_hi ≤ rarity_potential_cap(rarity)`
- Narrowing is monotonic: new lo ≥ old lo, new hi ≤ old hi, still contains `potential`
- Not listable for senior XI / marketplace sell / development drills while `in_academy` (015 rules retained)

**State transitions**:
```text
[seated] --daily growth--> [seated, higher OVR ≤ POT]
[seated] --assess scout--> [seated, tighter visible range]
[seated] --promote--> [senior, in_academy=false]  # weekly promote cap
[seated] --release / auto-release--> [removed from club inventory]
[seated] --aging warn--> [seated + warning UI]
[seated 20+] --season decay--> [seated, POT−≤1 if unused headroom]
[seated age-out] --grace--> [pending] --expire--> [auto-release]
```

---

### Youth Academy Facility (`players.youth_academy_level`)

| Level | Capacity | Notes |
|-------|----------|--------|
| 1 | 3 | No Legendary weight |
| 2 | 3 | |
| 3 | 4 | |
| 4 | 4 | |
| 5 | 5 | Legendary ~0.1% unless kill switch |

Also drives: rarity weight table, **initial** scout-range width, daily growth speed, advisory ready OVR. Upgrades **must not** mutate existing prospects’ rarity/POT/bounds identity (bounds already set stay; future seats use new width).

---

### Weekly Intake Event (`youth_intake_log`)

Existing PK `(owner_id, intake_week)`. Behavior change only:
- Generate/seat at most `youth_intake_count` (default **2**)
- Seat count = `min(count, max(0, capacity − occupied))` with grandfather over-cap ⇒ free seats treat `capacity − occupied` as ≤0 when occupied > capacity
- Idempotent per UTC week

---

### Scout Assessment Job

**Preferred shape** (new):

| Field | Notes |
|-------|--------|
| `id` | uuid |
| `owner_id` | club |
| `card_id` | seated prospect |
| `tier` | quick \| standard \| deep |
| `finishes_at` | timestamptz |
| `status` | pending \| completed \| cancelled |
| `created_at` | |

Club-level `players.scouting_finishes_at` / `scouting_active_tier` may remain for **discovery** only, or be superseded — do not allow two conflicting assessments on the same `card_id`.

On complete: narrow `pot_visible_*` by tier table; bump `scout_assessment_level`; charge already taken at dispatch via `apply_club_economy`.

---

### Discovery Scout Report (rebalanced `scouting_reports` or successor)

Paid search producing **at most one** V2-generated seated prospect on sign:
- Respects free capacity (no seat ⇒ cannot sign)
- Increments weekly **signing** counter
- Same rarity integrity as intake
- Shortlist of three fully revealed cards is no longer the primary UX; if shortlist retained temporarily, fog POT to ranges until superseded

---

### Academy Weekly Actions

| Field | Notes |
|-------|--------|
| `owner_id` | bigint |
| `week_start` | date (UTC week trunc, same helper as intake) |
| `promotes_used` | int default 0 |
| `paid_signings_used` | int default 0 |

Unique `(owner_id, week_start)`. Caps from `game_config` (`academy_weekly_promote_cap` default 2, `academy_weekly_paid_sign_cap` configurable).

---

### Graduation (event, not table)

Successful promote returns payload for milestone embed: name, OVR, rarity, age, time developed (`now − academy_seated_at`). No separate graduation inventory.

---

## `game_config` keys (new / changed)

| Key | Default (proposed) | Purpose |
|-----|--------------------|---------|
| `youth_intake_count` | **2** (was 3) | Free Monday seats attempted |
| `academy_slot_caps` or SQL fn | 3,3,4,4,5 | Capacity by level |
| `youth_academy_rarity_weights_l1..l5` | JSON weights | Rarity distribution |
| `youth_academy_legendary_enabled` | true | Kill switch |
| `youth_academy_legendary_weight_l5` | 0.001 | L5 only |
| `academy_initial_range_width_l1..l5` | ints | Initial visible span |
| `scout_assess_narrow_quick/standard/deep` | ints | Points removed from span |
| `scout_deep_min_range` | 2 | Floor width after Deep |
| `academy_weekly_promote_cap` | 2 | FR-013 |
| `academy_weekly_paid_sign_cap` | (TBD in tasks, ≥1) | FR-016 |
| `academy_promote_fee` | 500 | Coins; 0 allowed |
| `academy_promote_first_free` | true | Still counts toward cap |
| `academy_ready_ovr_by_level` | JSON | Advisory only |
| `academy_age_warn` | 20 | UI warning |
| `academy_age_out` | 21 | Pending boundary (shift from force@20) |
| `academy_age_out_grace_hours` | e.g. 72 | Auto-release delay |
| `academy_aging_decay_max` | 1 | Per season event |
| `youth_academy_v2_enabled` | false→true | Rollout flag |
| `youth_academy_generation_version` | 2 | Observability |

Validation on load (FR-021): weights non-negative and sum ~1.0 (or 100); Legendary weight 0 if disabled; capacity non-decreasing; bands within caps; costs/durations ≥ 0.

---

## Cutover rules

1. **Illegal POT, legal OVR**: set `potential = min(potential, rarity_cap)`; if `potential < overall` impossible under legal OVR — escalate OVR>cap rows to global 049 handling (do not invent rarity).
2. **Init ranges**: for each `in_academy` card, set lo/hi containing true POT using current YA level width (or migration width table).
3. **Origin**: set `academy_origin = 'migration'` where null.
4. **Over-capacity**: no deletes; acquisition RPCs check `occupied < academy_slot_cap(level)` (strict); UI shows occupied/cap even when occupied > cap.
5. **Generation version**: new seats stamp version 2 when flag on.

---

## Relationships (summary)

```text
players 1──* player_cards (in_academy seats)
players 1──* youth_intake_log
players 1──* academy_weekly_actions
player_cards 1──* academy_scout_assessment_jobs (0..1 active)
players 1──* scouting_reports (discovery; rebalanced)
```
