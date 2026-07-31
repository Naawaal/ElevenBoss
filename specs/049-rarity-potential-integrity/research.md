# Research: Rarity Potential Cap Integrity (`049`)

**Date**: 2026-07-31  
**Spec**: [spec.md](./spec.md)  
**US citation**: **US-42.2** / **US-42.7** / **US-42.9** (player state, economy integrity, DB invariants)

## R1 — Confirmed root causes (code evidence)

**Decision**: Treat rarity POT caps as **not currently invariant**. Multiple independent writers and one generation escape hatch create illegal POT; consumers then spend the illegal headroom.

| Path | Evidence | Failure mode |
|------|----------|--------------|
| `generate_potential` | `potential.py` returns `max(MIN, overall, pot)` after `min(..., rarity_cap)` | Illegal OVR forces POT above rarity |
| `apply_dynamic_potential_boost` | No rarity arg; ceiling `min(99, base+10)` | Epic can grow toward 99 |
| `process_match_result` | Latest repo def in `047_audit_remediation.sql`: `LEAST(99, LEAST(v_pot+boost, v_init_pot+10))` — **no rarity** | Production POT writer |
| `regen_pool.generate_regen_from_retired` | `min(94, ...)` then `model_copy` overwrites factory POT | P0 bypass of factory |
| `youth_intake.generate_youth_intake_cards` | Academy tier `pot_max` up to **94** on **Common** cards + gem +5; `model_copy` overwrite | Common POT > 75 |
| `CreatedPlayerCard` | Validates 1–99 only | `model_copy` can stay “valid” while illegal |
| `register_new_player` | `IF v_pot < overall THEN v_pot := overall` (latest `074`) | Raises POT; no rarity check |
| `claim_daily_pack` | `082` inserts COALESCE(pot, base, ovr) — no rarity | Trusts payload |
| `process_youth_intake` / `sign_youth_scout_prospect` | Raise POT to OVR; no rarity (`060` / `086`) | Same ingress anti-pattern |
| Progression RPCs | `allocate_skill_point` (`075`), `process_stat_drill` (`078`), `claim_evolution_reward` (`075`), academy growth (`060`) | Gate on **stored** POT |

**Alternatives considered**: Blame only dynamic POT (incomplete — regen/youth/register independent); blame display-only (rejected — progression consumes POT).

**Implementation gate**: Before rewriting SQL, run `pg_get_functiondef` on live/dev for every listed RPC — repo migrations can be superseded.

---

## R2 — Canonical mapping (single law, dual host)

**Decision**: Freeze caps as product law:

| Rarity | Cap |
|--------|----:|
| Common | 75 |
| Rare | 85 |
| Epic | 92 |
| Legendary | 99 |

- **Python**: `packages/player_engine/player_engine/potential.py` — add `rarity_potential_cap` (KeyError on unknown), `clamp_potential`, `validate_potential_integrity`. Do **not** use `.get(rarity, 75)` for enforcement.
- **SQL**: immutable `public.rarity_potential_cap(text)` returning NULL for unknown (CHECK fails closed).
- **Parity test**: DB-backed loop over `RARITY_POT_CAPS` must match SQL.

**Alternatives considered**: SQL-only enforcement (too late for generators); Python-only (RPC ingress still writable); soft default Common for unknown rarity (hides bugs — rejected).

---

## R3 — Generation vs legacy escape

**Decision**: `generate_potential` must **reject** `overall > rarity_cap` instead of manufacturing `POT = OVR > cap`. Remove the legacy comment that allows OVR to override rarity. Historical corruption belongs in repair tooling, not normal generation.

`create_player_card` / gacha / support legendary: call shared validate after construction; reject illegal target OVR before balancing.

**Alternatives considered**: Silent clamp of OVR on create (hides caller bugs); keep legacy escape (rejects FR-003).

---

## R4 — Dynamic POT

**Decision**: Extend `apply_dynamic_potential_boost(..., rarity)`:

```text
ceiling = min(rarity_cap, base_potential + MAX_DYNAMIC_BOOST)
return min(current + boost, ceiling)
```

SQL `process_match_result` must SELECT `rarity` and use:

```text
LEAST(rarity_potential_cap(rarity), v_pot + boost, v_init_pot + 10)
```

Keep youth eligibility (age 16–21, ratings, RNG) unchanged — only the ceiling changes.

---

## R5 — Regen + youth overwrite

**Decision**:
- Regen: replace hard `94` with `rarity_potential_cap(rarity)`; never assign POT without clamp+validate; prefer constructing legal POT before/with factory rather than unchecked `model_copy`.
- Youth: keep Common rarity generation (no academy rarity redesign). Apply `clamp_potential(candidate, rarity)` after academy tier roll and after gem bump. **Intentional behavior change**: YA tier tables currently advertise `pot_max` 82–94 (`facility_effects.YOUTH_ACADEMY_TIERS`); for Common that becomes **≤75**. Document in change_log — not a new feature, an integrity correction.
- If Pydantic `model_copy` skips validators in current pydantic version, either validate explicitly after copy or rebuild via constructor — confirm in implementation (pytest on Epic POT 97 copy).

---

## R6 — Ingress RPCs: reject, don’t raise POT

**Decision**: For `register_new_player`, `claim_daily_pack`, `process_youth_intake`, `sign_youth_scout_prospect`:

1. Resolve rarity cap (NULL → reject unsupported rarity).
2. Reject if OVR > cap, POT > cap, base POT > cap, or OVR > POT.
3. **Delete** the `IF pot < overall THEN pot := overall` anti-pattern.

Malformed service-role payloads must fail before INSERT.

---

## R7 — Progression consumers: effective POT

**Decision**: During and after rollout:

```text
v_effective_pot := LEAST(stored_potential, rarity_potential_cap(rarity))
```

Use in allocate / drill / evolution claim / academy growth / fusion paths that gate on POT / mentor source-target checks that assume POT. Keep soft-fail drill XP behavior; only the **stat boost** ceiling uses effective POT.

After constraints validated, stored POT is legal, but retaining effective-POT in high-value mutators is defense in depth (FR-008).

Python mirrors: `progression_gates.py`, `mentor_math.py` callers should pass legal/effective POT from bot layer or clamp inside helpers.

---

## R8 — Persistence: CHECK not silent triggers

**Decision**: After repair, add NOT VALID then VALIDATE:

- `player_cards_potential_rarity_cap_chk`
- `player_cards_base_potential_rarity_cap_chk`
- `player_cards_overall_potential_chk`
- Optional diagnostic: `overall <= rarity_potential_cap(rarity)`

Two migrations:

| File | Contents |
|------|----------|
| `088_rarity_potential_guards.sql` | SQL cap fn; rewrite writers/consumers/ingress; audit table + RLS; optional NOT VALID CHECKs; game_config flag; verify guard entries |
| `089_validate_potential_integrity.sql` | VALIDATE CONSTRAINT; final schema assertions |

**Alternatives considered**: One mega migration (rejected — irreversible mix of repair+validate); BEFORE trigger that clamps (hides bugs — rejected by spec).

---

## R9 — Repair + reimbursement

**Decision**:
- Categories A/B/C as spec.
- Stat rollback: prefer ledger attribution; else `balance_true_ovr` toward `min(legal_pot, rarity_cap)`.
- Refund only removed paid progression; coins/energy via `apply_club_economy` with idempotency keys `potential_cap_fix:<batch>:<card>:<kind>`; SP atomic with spent counters.
- Confidence: **EXACT** (e.g. drill `apply_club_economy` metadata with `card_id`/`drill_id`/`cost`), **RECONSTRUCTED** (aggregate `skill_points_spent`), **MANUAL_REVIEW** (fusion/items/payer ambiguity).
- **Non-negotiable**: dry-run report before production mutation; `MANUAL_REVIEW` policy resolved first.
- Mentor: no auto-reverse; integrity assert before transfer.
- Marketplace damages: out of scope (export list only).
- Audit table `potential_cap_repair_audit` with `UNIQUE(batch_id, card_id)`.

Reuse patterns from `scripts/fix_inflated_player_stats.py` / `balance_true_ovr`; do **not** reuse `scripts/recalculate_potentials.py` as-is (it calls current `generate_potential` and would re-corrupt if escape remains).

---

## R10 — Feature flag

**Decision**: Temporary `game_config` key `potential_rarity_caps_enabled` (bool):

- `false` (shadow): compute legal cap / log would-block; optional for app-layer only
- `true` (enforce): progression + generators enforce

SQL CHECK constraints, once VALIDATED, are permanent and **must not** be gated by this flag. Delete flag after incident close.

---

## R11 — Monitoring

**Decision**: No new dashboard. Anomaly SQL (`COUNT` of violations) at: deploy verify, bot startup, after youth/regen/academy growth/season aging/match processing. Non-zero → `CRITICAL: potential_integrity_violation` + card ids; **no auto-repair**.

---

## R12 — Containment before fairness

**Decision**: Ship P0 prevention (Python + migration 088 RPC guards) before production repair/refunds. Historical dry-run can proceed in parallel on a clone once `rarity_potential_cap` exists.

---

## Resolved clarifications

No open `NEEDS CLARIFICATION`. Product choices locked by input plan + spec: reject-not-raise, CHECK-not-trigger, dry-run confidence labels, mentor non-reversal, marketplace damages out, academy rarity redesign out (clamp only).

---

## Live defs (implement T001 — 2026-07-31)

Probed via `pg_get_functiondef` against `DATABASE_URL` before 088:

| Function | Notes vs repo |
|----------|----------------|
| `process_match_result(...)` | Live matched `047` pattern: `LEAST(99, …)` dynamic POT, **no rarity** |
| `register_new_player` | Live had `IF v_pot < overall THEN v_pot := overall` |
| `claim_daily_pack` | Live matched `082` (no rarity assert) |
| `allocate_skill_point` / `process_stat_drill` / `claim_evolution_reward` | Gated on stored POT only |
| `process_youth_intake` / `sign_youth_scout_prospect` | Raise-POT-to-OVR pattern |
| `process_daily_academy_growth` | Ceiling from stored POT |
| `train_with_fodder(bigint,uuid,uuid)` | Single fodder id (not uuid[]) |
| `transfer_mentor_xp` | Present; no rarity assert |

Dumps saved under `scratch/live_rpc_defs_049/` for migration authoring. Migration **088** applied from those dumps + patches.
