# Contract: Academy rarity generation V2

**Feature**: `051-youth-academy-rarity`  
**RPCs / modules**: `generate_youth_intake_cards` (Python), discovery finalize generator, `process_youth_intake`, `sign_youth_scout_prospect` (or successor), SQL `assert_card_potential_integrity` / `rarity_potential_cap`

## Rules

1. Order: **roll rarity** from YA-level weights → roll OVR in level band → roll POT in rarity band with `OVR ≤ POT ≤ rarity_potential_cap(rarity)`.
2. Legendary weight is **0** unless `youth_academy_level = 5` and Legendary enabled.
3. No pity. No post-seat rarity/POT reroll on facility upgrade.
4. RPC ingress: reject payloads that fail integrity or Legendary-at-L&lt;5; do not raise POT to fix OVR; do not upgrade rarity to preserve illegal POT.
5. Free intake seats `min(youth_intake_count, free_seats)` with `free_seats = max(0, cap − occupied)`; over-cap clubs have `free_seats = 0`.
6. Default `youth_intake_count = 2`. Idempotent via `youth_intake_log` UTC week.

## Outputs

- Seated cards: `in_academy=true`, progress 0, seated_at now, origin `weekly_intake` or `paid_scout`, visible bounds initialized.
- Response includes seated ids + skip reason when capacity blocked (`capacity_blocked`).

## Non-goals

Senior-roster dumping; backlog claim pile; client-trusted POT as SoT.
