# Contract: Scout assessment ranges

**Feature**: `051-youth-academy-rarity`  
**Surfaces**: Academy hub list, assess buttons, discovery shortlist (fogged), intake DM

## Assessment lifecycle

1. **Dispatch** `(owner_id, card_id, tier)` — verify seated ownership; reject if active assessment on card; charge via `apply_club_economy` with idempotency key; set finishes_at from tier hours.
2. **Finalize** — narrow `pot_visible_lo/hi` by tier table; assert still contains `potential`; never widen; update `scout_assessment_level`; no attribute/rarity/POT identity changes.
3. **Deep default** — resulting width ≥ `scout_deep_min_range` (default 2) unless a separate late-complete config explicitly allows 0–2 exact reveal (off by default).

## Display

| Surface | Show |
|---------|------|
| Academy list | name, age, position, OVR, rarity, **range**, progress, readiness estimate, stars from **interval** |
| Deep complete | tight range + outlook — **not** `📊 {exact} POT` as default |
| Intake / discovery | ranges; no exact POT dump |

## Conflicts

- Second dispatch on same card while pending → error, no charge.
- Finalize after promote/release → no-op / safe fail; no second charge.

## Discovery (separate)

Paid discovery may still add a prospect under capacity + weekly signing cap; generated card initializes ranges like intake. Do not present discovery as “exact Deep POT shortlist of three” as the primary UX.
