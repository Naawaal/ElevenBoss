# Implementation Plan: Rarity Potential Cap Integrity

**Branch**: `049-rarity-potential-integrity` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/049-rarity-potential-integrity/spec.md`

**US citation**: **US-42.2** (player state) · **US-42.7** (economy integrity — refunds via `apply_club_economy`) · **US-42.9** (DB invariants / CHECK). Extends progression/economy single-pipe rules (US-23 / US-25). No new XP or coin pipes.

## Summary

Rarity POT ceilings (Common 75 / Rare 85 / Epic 92 / Legendary 99) are design intent but not an invariant: generation can raise POT to match illegal OVR, dynamic match POT and regen/youth overwrite ignore rarity, and ingress RPCs raise POT when below OVR. Progression then spends illegal headroom. Plan: central Python+SQL cap helpers; fix all producers and consumers; two-phase migrations (`088` guards + audit, `089` VALIDATE CHECKs); mandatory dry-run reimbursement report with EXACT/RECONSTRUCTED/MANUAL_REVIEW before any production repair; refund only removed paid progression; notify managers after commit. No new gameplay features.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `player_engine.potential`, `CreatedPlayerCard`, `regen_pool`, `youth_intake`, `player_factory.balance_true_ovr`, progression RPCs (`process_match_result`, `allocate_skill_point`, `process_stat_drill`, `claim_evolution_reward`, academy/youth/pack/register), `apply_club_economy`, `game_config`

**Storage**: New audit table `potential_cap_repair_audit` (+ RLS); new SQL fn `rarity_potential_cap(text)`; CHECK constraints on `player_cards`; optional `game_config.potential_rarity_caps_enabled`. Migrations **088** then **089** (repo head is **087**).

**Testing**: pytest unit (caps, dynamic, generation reject, regen/youth property); DB contract parity Python↔SQL; ingress reject tests; progression boundary tests; repair dry-run + double-run idempotency on clone

**Target Platform**: Discord bot + hosted Supabase

**Project Type**: Stability / game-integrity correction (containment → audit → repair → lock)

**Performance Goals**: Cap helpers O(1); repair is offline/ops batch, not hub hot path; anomaly COUNT cheap with existing indexes on `player_cards(rarity)` if needed later

**Constraints**: Fail closed (reject illegal OVR/POT); never raise POT above rarity to accommodate OVR; no silent clamp triggers; no parallel economy/XP pipes; dry-run before production mutate; YAGNI — no dashboard / no new slash commands; academy rarity redesign out of scope (clamp only)

**Scale/Scope**: ~1 package module + several generators; ~8–12 RPC rewrites in 088; 1 ops repair script family; DM notifier reuse; `verify_required_schema.sql` + tests; `change_log.md`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Cap math + validation in `packages/player_engine`; Discord DM/notify in `apps/discord_bot/`; no `discord` in packages |
| II. DB via RPC / atomic economy | PASS | Mutations via rewritten RPCs; refunds via `apply_club_economy` + idempotency keys; repair script uses RPCs/ledger not raw coin UPDATEs |
| III. Typing / Pydantic | PASS | `CreatedPlayerCard` model validator; typed helpers |
| IV. Slash + defer | PASS | No new commands; notify after repair (ops/batch), not a new hub |
| V. APScheduler | PASS | Optional anomaly check hooks on existing lifecycle jobs — no new gameplay job |
| VI. Friendly errors | PASS | Ingress/progression raise clear domain errors; manager DM template in contracts |
| VII. YAGNI | PASS | Integrity only; academy rarity redesign / marketplace damages deferred |

**Post-Phase 1 re-check**: PASS — dual Python/SQL maps justified (persistence SoT); audit table is incident evidence not gameplay; CHECK-not-trigger locked in research.

## Project Structure

### Documentation (this feature)

```text
specs/049-rarity-potential-integrity/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── rarity-potential-invariant.md
│   ├── card-ingress-reject.md
│   ├── progression-effective-pot.md
│   └── repair-reimbursement.md
└── tasks.md                # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/potential.py          # rarity_potential_cap, clamp, validate; fix generate + dynamic
packages/player_engine/player_engine/created_card.py        # model validator → validate_potential_integrity
packages/player_engine/player_engine/player_factory.py      # reject target_ovr > cap; post-validate
packages/player_engine/player_engine/regen_pool.py          # rarity cap; no illegal overwrite
packages/player_engine/player_engine/youth_intake.py        # clamp after academy/gem
packages/player_engine/player_engine/progression_gates.py   # effective POT (min stored, cap)
packages/player_engine/player_engine/__init__.py            # exports
# audit other generators: procedural_generator, gacha paths, support legendary

supabase/migrations/088_rarity_potential_guards.sql        # NEW
supabase/migrations/089_validate_potential_integrity.sql   # NEW — after repair
supabase/scripts/verify_required_schema.sql                # extend guards

scripts/potential_cap_audit.py                             # NEW — read-only inventory + dry-run report
scripts/potential_cap_repair.py                            # NEW — apply repair/refunds (clone first)
# fix or retire unsafe: scripts/recalculate_potentials.py

apps/discord_bot/…                                         # anomaly log on startup / lifecycle; DM batch after repair
# reuse level_reward_notifier / DM patterns — no new slash command

tests/test_potential_generation.py                         # extend
tests/test_rarity_potential_integrity.py                   # NEW — unit + property
tests/test_rarity_potential_sql_parity.py                  # NEW — DB contract (optional skip if no DATABASE_URL)
change_log.md                                              # player-facing integrity + YA Common clamp note
```

**Structure Decision**: Pure rules in `player_engine`; persistence/RPC authority in migrations; ops scripts under `scripts/` (not imported by production cogs). Agent-context update script absent — skipped (same as `048`).

## Complexity Tracking

> Dual host mapping is intentional, not a constitution violation.

| Choice | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| Python + SQL `rarity_potential_cap` | Generators are Python; mutations are SQL | Single side leaves the other open |
| Two migrations (088 / 089) | Repair must finish before VALIDATE | One migration mixes mutate+lock irreversibly |
| Audit table | Incident evidence + idempotent refunds + DM tracking | Log-only files are not durable / replay-safe |
| Effective POT in consumers | Protects during dirty-data window | Wait for full repair leaves leak open |
| Temporary game_config flag | Shadow → enforce rollout | Permanent “disable caps” switch (forbidden) |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Implementation sketch (for tasks handoff)

### P0 — Containment

1. Add `rarity_potential_cap` / `clamp_potential` / `validate_potential_integrity`; fix `generate_potential` (reject OVR > cap); fix dynamic boost + callers.
2. `CreatedPlayerCard` invariant; fix regen / youth / factory / other generators; harden `recalculate_potentials` or mark unsafe.
3. Migration **088**: SQL cap fn; rewrite `process_match_result` dynamic POT; reject-not-raise on register/pack/youth/scout; effective POT in allocate/drill/evolution/academy/fusion; audit table + RLS; `game_config` flag; NOT VALID CHECKs optional; schema guard entries.
4. Unit + property tests; Python↔SQL parity test.

### P1 — Quantify

5. Live `pg_get_functiondef` audit; repo-wide POT write grep classification.
6. `potential_cap_audit.py` inventory + dry-run reimbursement report (confidence labels). Resolve MANUAL_REVIEW policy offline.

### P2 — Repair (clone → prod)

7. Repair tool: Category A/B/C; `balance_true_ovr`; economy/SP refunds idempotent; double-run idempotency.
8. Production window: contain → snapshot → repair → refund → anomaly 0 → notify.
9. Migration **089**: VALIDATE constraints; verify script.
10. Startup/lifecycle anomaly monitors; `change_log.md`.

### Explicit non-goals

Academy rarity redesign; marketplace damages math; mentor auto-reversal; new hubs/commands/dashboards.
