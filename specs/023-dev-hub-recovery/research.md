# Research: Development Hub Recovery

**Feature**: `023-dev-hub-recovery`  
**Date**: 2026-07-17

## R1 — Batch mutation: one RPC vs N× `process_recovery_session`

**Decision**: Add atomic `process_recovery_batch(p_owner_id, p_card_ids UUID[])` (length 1–3). Single energy debit for the full total; all cards updated in one transaction; reject entire batch if any card fails eligibility or energy is insufficient.

**Rationale**: Spec FR-009 / SC-004 require all-or-nothing (insufficient energy → zero of three recover). Sequential bot-side RPC calls can charge energy for card 1 then fail card 2, leaving a partial success the manager did not confirm. Constitution II prefers one transactional RPC over app-level loops of mutations.

**Alternatives considered**:
- Call existing `process_recovery_session` three times — rejected (partial failure / double-tap races).
- Pre-check energy in Discord then loop — rejected (TOCTOU; still not one transaction).

## R2 — Detach Recovery from skill-drill daily slots

**Decision**: Batch (and any retained single-card path) MUST NOT increment `players.daily_drill_count` or `player_drill_daily_log`. Pacing is **action energy only** (FR-012).

**Rationale**: Spec intentionally decouples fitness from skill-drill capacity so Recover is not “using a drill slot.” Current `process_recovery_session` (062) still shares those caps — that behavior is superseded for this feature.

**Alternatives considered**:
- Keep sharing drill caps for continuity with 009 FR-006 — rejected by 023 FR-012 and product intent (“no longer a drill”).
- Add a separate daily Recover cap — rejected (YAGNI; energy is enough).

## R3 — Fate of `process_recovery_session`

**Decision**: After drills UI removal, either (A) rewrite the single-card function as a thin wrapper that calls `process_recovery_batch` with a one-element array and **no drill-cap side effects**, or (B) `DROP` it once grep shows zero callers. Prefer (A) for one release if any scratch/scripts still call the old name.

**Rationale**: Avoid leaving a drills-cap path live that UI no longer shows but scripts might still hit.

**Alternatives considered**: Leave old body unchanged — rejected (would reintroduce drill-slot consumption if anything still calls it).

## R4 — Discord multi-select UX

**Decision**: Use one `discord.ui.Select` with `min_values=1`, `max_values=3`, up to 25 options. Option description shows fatigue % (and OVR). Flow: select → **Continue** → confirmation embed (names, +fatigue, total ⚡) → **Confirm** / **Cancel** → on success followup + `show_hub`. Mirror Mentor Transfer’s short-lived, owner-checked, deferred pattern.

**Rationale**: Discord native multi-select matches “1 to 3” without checkboxes or custom state machines. Confirm step satisfies FR-006.

**Alternatives considered**:
- Three sequential single-player recovers — rejected (worse UX; doesn’t match spec).
- Persistent views registered in `main.py` — rejected (v1 hub subviews are message-bound like Mentor).

## R5 — Eligibility extras beyond FR-004

**Decision**: Keep existing RPC gates for **active evolution** and **transfer list** (from current `process_recovery_session`). UI should filter them out of the select when practical so managers don’t hit opaque errors.

**Rationale**: Not product expansion — preserving safety already shipped in 062. Spec FR-004 lists the manager-facing exclusions; evo/transfer remain engineering continuity.

**Alternatives considered**: Allow Recover while listed/evolving — rejected (would fight transfer/evo locks elsewhere).

## R6 — Energy accounting

**Decision**: Total cost = `len(selected) × get_game_config_int('fatigue_recovery_energy', 5)`. One `apply_club_economy(..., -total, 'recovery_session' | 'recovery_batch', ...)` call. Per-player fatigue grant from `fatigue_recovery_session` (40). Return applied deltas after clamp.

**Rationale**: Matches Assumptions in spec; config already exists from 010 (energy=5).

**Alternatives considered**: Flat 5⚡ for any batch size — rejected (spec says per player / total scales with N).

## R7 — Pure helpers

**Decision**: Add small helpers in `packages/player_engine/fatigue.py`: `recovery_session_eligible(card-like)` and `recovery_batch_energy(n, per_player=5)`. Reuse `apply_recovery_session` for clamp math in tests. No Discord imports.

**Rationale**: Testable without bot; keeps cogs thin.

## R8 — Rollback

**Decision**: Document rollback as: restore prior `process_recovery_session` body (drill caps optional restore only if rolling product UX back to drills); remove hub Recover UI; re-add drills Recovery option from git history. Do **not** reverse Hospital/passive migrations.

**Rationale**: Spec Assumptions; Ponytail relocation is reversible at the UX + RPC boundary.

## Resolved clarifications

No open NEEDS CLARIFICATION items remain from Technical Context. Spec Assumptions (5×N energy, no drill slots, roster not XI) are adopted as plan defaults.
