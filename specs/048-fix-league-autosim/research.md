# Research: Fix League Expired Auto-Sim (`048`)

**Date**: 2026-07-31  
**Spec**: [spec.md](./spec.md)

## R1 — Root cause

**Decision**: Treat **silent eligibility skip** in `run_league_match_simulation` (via `human_club_xi_ok`) when called from `auto_sim_expired_fixtures` as the primary production hole.

**Evidence**: Season #2 MD5 pending fixtures have no `match_runs`; Bhavs FC™ and Dragon Club have past-grace starters in XI; skip returns without marking `is_played`. UI string “Expired (Pending Auto-Sim)” is cosmetic only.

**Alternatives considered**: Blaming scheduler (legacy job does run for `pacing_mode=legacy`); blaming Dynamics-only path (this season is legacy). Secondary: missing threads causing early `return 0` before any fixture loop work — harden with silent sim for **eligible** sides.

---

## R2 — Fallback rule when human ineligible after window end

**Decision (locked)**: Reuse **026 / lifecycle** forfeit rules already implemented:

| Home legal | Away legal | Outcome |
|------------|------------|---------|
| Yes | Yes | Auto-sim (NSS path) |
| No | Yes | `single_forfeit(illegal_is_home=True)` → **0–3** |
| Yes | No | `single_forfeit(illegal_is_home=False)` → **3–0** |
| No | No | `double_forfeit()` → **0–0** `double_forfeit` |

- AI clubs are always **legal** for this check (generated squad / existing AI path).
- Eligibility = existing `human_club_xi_ok` (11 starters, not `squad_invalid`, no past-grace contracts in XI).
- **Do not** invent assistant repair in this hotfix (lifecycle V1 has richer lineup repair; legacy saved XI + forfeit-if-illegal is enough and matches “cannot field legal team” intent for post-window).

**Rationale**: Spec 026 + `forfeit_rules.py` + lifecycle `_resolve_fixture` already encode the product rule; absence-vs-outage forbids inventing forfeits from outages, not from illegal teams after deadline.

**Alternatives considered**: Admin 1–0; leave pending until renew (rejects SC-001/002); force sim with illegal cards (violates contract gates).

---

## R3 — Where to wire

**Decision**: New helper `settle_expired_fixture` used by `auto_sim_expired_fixtures` (hub open + 10-min job + any Dynamics tick that already calls the same function). Prefer **not** changing the mid-match skip inside `run_league_match_simulation` for live Play (live Play should still refuse illegal XI). Only **post-window** settle applies forfeit.

**Alternatives considered**: Always `skip_xi_gate=True` on auto-sim (would play illegal contracts — rejected); only change UI (rejected).

---

## R4 — Discord threads / guild availability

**Decision**:
- **Guild unreachable** → keep current pause/skip (no sporting forfeit) — FR-007 / absence-vs-outage.
- **Guild OK, threads missing** → for **eligible** fixtures, run sim with **silent handler** (lifecycle already does this); for **forfeit**, write DB only (no threads needed).
- Do not require commentary threads to clear Pending forever.

---

## R5 — Settle-once

**Decision**: Before writing forfeit or starting sim, re-read fixture `is_played` / active `match_runs`. Fixture update for forfeit should be conditional on `is_played=false` (and ideally status not already terminal). Standings are derived from played fixtures in `fetch_standings` — no separate points pipe required for Season Pts.

**Weekly `players.league_points`**: Normal auto-sim updates weekly LP via match rewards path; forfeit path may **not** grant match XP/coins (sporting table only) unless an existing lifecycle forfeit already does — match lifecycle: forfeit write only, no NSS rewards. Document in contract.

---

## R6 — Fixtures UI

**Decision**:
- Played + `result_type in (forfeit, double_forfeit)` → show score + **Forfeit** / **Double Forfeit** label (not “Full Time” alone).
- Expired + unplayed → keep Pending only if settle has not yet succeeded this cycle; after forfeit/sim, show result.
- Optional: if still unplayed and human ineligible, append short “blocked: {club} — renew/replace XI” from `club_xi_block_reason` (best-effort, ephemeral fixtures view).

---

## R7 — Migration

**Decision**: **No migration** unless implement discovers missing columns (unlikely — `result_type`, `resolved_by`, `status`, `played_at` exist). Prefer app-layer updates mirroring lifecycle.

---

## Resolved clarifications

Fallback rule locked to 026 single/double forfeit — no open `NEEDS CLARIFICATION`.
