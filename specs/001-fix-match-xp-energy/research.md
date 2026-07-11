# Research: Fix Match XP + Energy Regen

## R1 — Why match XP fails on bot/league

**Decision**: Treat missing/broken `apply_card_xp` SECURITY DEFINER (migration 048 after 047 revoked `player_xp_log` INSERT for anon) as the primary hard-failure root cause; treat daily 100 XP/card cap as expected silent zero; fix league recovery missing `name` as a secondary KeyError path.

**Rationale**:
- Migration 047 revoked anon/authenticated writes on `player_xp_log` and made `apply_club_economy` DEFINER, but left `apply_card_xp` as invoker until 048.
- `change_log.md` documents production symptom: `permission denied for table player_xp_log`.
- Bot + league both call `apply_match_xp_if_needed` → `process_match_result` → `apply_card_xp`.
- Friendlies intentionally skip XP (footer + no call site).
- League recovery builds `{"id": cid}` only → `build_process_match_result_rpc` does `card["name"]` → KeyError.

**Alternatives considered**:
- Rewriting XP into a new RPC — rejected (violates single XP pipe / YAGNI).
- Granting friendly XP — rejected (spec FR-007 / design).
- Raising daily cap — rejected (FR-009; pacing, not this bug).

## R2 — Energy “10hr” complaint

**Decision**: Ship approved 046 target (`energy_regen_per_min = 0.25` → 1 per 4 min → 400 min ≈ 6h 40m empty→full) and align bot display constants/copy. Do not change store coin refill.

**Rationale**:
- Baseline 028: `0.1666667` → 1/6 min → 600 min = 10h (matches report).
- 046 already seeds `0.25`; rebalance proposal / US-35 already approved this.
- Bot `REGEN_PER_MIN = 1/6` and `api_errors.py` still advertise 6 minutes even if DB is updated — UI drift is a real bug.
- Store refill has no time cooldown (3/day coin purchases) — not the “10hr” lever.

**Alternatives considered**:
- Faster than 046 (2–4h full) — rejected by stakeholder choice (option A).
- Lowering `energy_max` — rejected (larger economy ripple; not requested).

## R3 — FR-004 hard-failure UX

**Decision**: Keep `apply_match_xp_if_needed` re-raising on RPC failure; ensure bot/league cog paths show `error_embed` / followup with a clear XP-related message when the failure is from the XP step. Do not mark `xp_applied_at` on failure (already true — mark only after success).

**Rationale**:
- Current code re-raises after debug_log; bot path wraps simulation in broad `except` with `api_error_message`.
- Economy may already have committed before XP — acceptable for this fix; messaging must not claim full success if XP failed.
- Silent daily-cap zero must remain silent success (FR-003), distinct from hard fail.

**Alternatives considered**:
- Compensating transaction rolling back coins on XP fail — out of scope / high risk.
- Post-match XP breakdown embed for every match — optional; not required if hard fails already surface.

## R4 — Schema verify gap

**Decision**: Extend `verify_required_schema.sql` to assert `apply_card_xp` is SECURITY DEFINER (`prosecdef`), so missing 048 fails deploy checks even when the function exists.

**Rationale**: Existence-only checks currently pass without 048 applied.

**Alternatives considered**: Making `process_match_result` DEFINER too — optional hardening, not required if `apply_card_xp` is DEFINER.

## R5 — Display regen source of truth

**Decision**: Default sync helpers to `1/4` (0.25) matching 046; where an async DB handle exists, prefer `get_game_config_numeric('energy_regen_per_min', 0.25)` so ops can tune without another bot deploy. Smallest change that fixes stale 10h copy.

**Rationale**: Lazy senior — one constant flip fixes the bug; optional config read prevents future drift (same pattern as `get_match_energy_cost`).

**Alternatives considered**:
- Only update `game_config` and leave bot hardcoded — rejected (FR-006 fails).
- Full config-driven rewrite of all energy strings — unnecessary scope.
