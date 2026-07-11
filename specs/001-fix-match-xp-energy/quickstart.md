# Quickstart: Validate Match XP + Energy Regen

## Prerequisites

- Repo checkout with feature changes applied
- `DATABASE_URL` / Supabase project where migrations can be verified
- Bot able to run bot + league match paths (or unit tests covering the same contracts)
- Cards under daily match-XP cap for positive XP checks

## 1. Schema guards

```bash
# Prefer project verify script / scratch helper
python scratch/verify_schema_full.py
# or
psql "$DATABASE_URL" -f supabase/scripts/verify_required_schema.sql
```

**Expect**:
- `apply_card_xp` exists and is SECURITY DEFINER
- `game_config.energy_regen_per_min` = `0.25` (apply migration 046 if not)

If DEFINER is false, apply `supabase/migrations/048_apply_card_xp_security_definer.sql`.

## 2. Unit tests

```bash
pytest tests/test_match_loop_hardening.py tests/test_economy_flows.py -q
# plus any new tests added for regen minutes-to-full / recovery hydration
```

**Expect**: minutes-to-full for 0/100 ≈ 400; XP payload builder accepts hydrated cards; no regressions on friendly “no XP” assumptions in existing tests.

## 3. Bot match XP (manual or staging)

1. Note starting XP/level on one starting-XI card (under daily cap).
2. Complete a bot match.
3. Re-check card XP/level — must increase (SC-001).
4. If RPC is forced to fail (staging only), manager must see an error indication (SC-006), and `xp_applied_at` must remain null.

## 4. League match XP

1. Complete a human league match with eligible cards.
2. Confirm XP increased (SC-002).
3. If testing recovery path: recovered run must hydrate card `name` before XP apply (no KeyError).

## 5. Energy display

1. With energy below max, open hub/status that shows `format_action_energy_status`.
2. At 0/100, time-to-full ≈ **6h 40m** (SC-003 / SC-004).
3. Trigger insufficient-energy message — copy references **4 minutes**, not 6.

## 6. Friendly sandbox

1. Play a friendly.
2. Confirm no energy spent and no XP granted (SC-005).

## 7. Cap behavior (not a bug)

After ~100 match XP on a card in one day, further bot/league matches complete with **0** additional match XP for that card (FR-003 / FR-009).
