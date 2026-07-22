# Research: Evolution Start Button Fix

**Feature**: `028-evolution-start-button` | **Date**: 2026-07-22

---

## R1 — Is the grey Start button a bug or intentional?

**Decision**: Treat as **both**. Disable-when-gated is intentional; **false disable after live cooldown** is a bug.

**Evidence**:
- `ClubEvolutionsHubView` sets `disabled=not can_start` from `get_evolution_hub_status`.
- Live embed: `0/3 slots` + `Next evolution available in 9h 23m` → cooldown gate only (slots free).
- `9h 23m` remaining fits a **10h** clock (~37m since last start), not a 6h clock.

**Alternatives**:

| Option | Rejected because |
|--------|------------------|
| Remove cooldown entirely | Product rule; out of scope |
| Always leave button enabled and toast on click | Worse UX for full slots; still need honest timer |
| Only fix Discord “unclickable” by never disabling | Loses clear disabled affordance; still wrong timer |

---

## R2 — Where does 10h vs 6h drift live?

**Decision**: Single source of truth = `game_config.evolution_cooldown_hours` (seeded **6** in migration 046). Hub status must read it the same way as `start_player_evolution`.

**Evidence**:
- `get_evolution_hub_status` defined only in `023_evolution_club_limits.sql` with `v_cooldown_hours CONSTANT INTEGER := 10` — never replaced later.
- `start_player_evolution` in `046` / `062`: `get_game_config_int('evolution_cooldown_hours', 10)`.
- Package mirror: `EVOLUTION_START_COOLDOWN_HOURS = 6` with comment pointing at 046 seed.
- Spec 018 FR-009 already required identical cooldown enforcement in RPC + UI; research called out config drift.

**Alternatives**:

| Option | Rejected because |
|--------|------------------|
| Change seed back to 10h to match hub | Undoes published 6h rebalance; player-facing changelog already aligned to 6h |
| Hardcode 6 in hub status | Reintroduces drift if operators tune `game_config` |
| Compute cooldown only in Python | Violates “server rules own eligibility”; start already enforces in SQL |

---

## R3 — Start cost copy `10×OVR` vs live formula

**Decision**: Update Evolution Command Center Resources line to `25 energy + (500 + 5×OVR) coins` (or equivalent wording from package / status fields). Also return flat + ovr mult from hub status so UI can prefer RPC values.

**Evidence**:
- Cog hardcodes ``10×OVR`` in `show_club_evolutions_hub`.
- Live start: `evolution_start_flat` (500) + `evolution_start_ovr_mult` (5).
- Hub status still returns hardcoded `start_coin_multiplier: 10` (unused by cog today, but misleading if used later).

**Alternatives**:

| Option | Rejected because |
|--------|------------------|
| Leave cost copy for a later ticket | Spec FR-006; same screen as the bug report |
| Show exact coins without OVR | Hub is club-level; formula is the honest club summary |

---

## R4 — Energy field (`training_energy` vs `action_energy`)

**Decision**: Prefer aligning hub status energy sync/read with **action energy** if the REPLACE is already touching the function; do not block the cooldown fix if dual-write still makes `training_energy` equal `action_energy` in prod.

**Rationale**: Start path uses `sync_action_energy`. Hub path still calls `sync_training_energy` and returns `training_energy`. User’s `55/120` suggests dual-write is working. Cool down/cost honesty is the P1 defect; energy label rename is secondary.

**Alternatives**:

| Option | Rejected because |
|--------|------------------|
| Large energy rename across all hubs | Out of scope for this bug |
| Ignore forever | Acceptable short-term if dual-write holds; note as follow-up if values diverge |

---

## R5 — Agent context update script

**Decision**: Skip `.specify` agent-context update — no agent-context script under `.specify/scripts/` in this repo (same as `022-v1-stability-blueprint` research note).

---

## Resolved Technical Context

| Item | Resolution |
|------|------------|
| Cooldown source | `game_config.evolution_cooldown_hours` via `get_game_config_int`, same defaults as start RPC |
| Migration number | `073_evolution_hub_status_config.sql` (next after 072) |
| UI cost | Package constants and/or new status `start_coin_flat` / `start_coin_ovr_mult` |
| New surfaces | None |
| NEEDS CLARIFICATION | None remaining |
