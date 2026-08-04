# Research: Youth Academy Rarity-Cap Redesign

**Feature**: `051-youth-academy-rarity`  
**Date**: 2026-08-04  
**Status**: Complete — all Technical Context unknowns resolved against live 015/049 code and `spec.md`.

---

## R1 — Generation model (rarity-first vs Common + gem)

**Decision**: Resolve **rarity first** from academy-level weight tables, then roll potential inside that rarity’s legal generation band and hard ceiling (`rarity_potential_cap`). Remove the Common-only factory + gem `+5 POT` path as the V2 default.

**Rationale**: Spec FR-002 and Feature 049 require `overall ≤ potential ≤ rarity ceiling`. Current `youth_intake.py` always emits Common and can advertise tier `pot_max` above 75 before clamp — correct for integrity clamp, wrong for product (no Rare/Epic/Legendary academy fantasy). Legendary only at YA L5 (~0.1%) with config kill switch satisfies FR-007.

**Alternatives considered**:
- Keep Common-only + clamp — fails rarity progression fantasy and SC-007 Legendary monitoring.
- Post-roll rarity from POT — inverts FR-002 and fights 049 producers.
- Pity Legendary — out of scope / forbidden by assumptions.

---

## R2 — Capacity curve and over-capacity cutover

**Decision**: Replace `academy_slot_cap` / `ACADEMY_SLOT_CAPS` **4/5/6/8/10** with **3/3/4/4/5**. Grandfather clubs above new cap: keep existing seats, show `occupied/cap` (e.g. 5/3), block free intake and paid discovery until `occupied ≤ cap`.

**Rationale**: FR-005 / FR-020 / SC-009. Forced delete or forced promote would violate fairness and US-6 auto-release philosophy.

**Alternatives considered**:
- Soft-migrate by auto-releasing lowest POT — feels punitive; not in spec.
- Keep old curve — fails primary retention goal.

---

## R3 — Scouting: assessment vs discovery

**Decision**: Split into two products that share coin tiers naming where useful:

1. **Assessment scout** (US-3 / FR-008–010) — operates on a **seated** `player_cards` id. Narrows `pot_visible_lo/hi` around true `potential`; never rerolls identity; Deep yields tight range (≈2–4), not exact POT by default; conflicting in-flight assessment rejected without double-charge.
2. **Discovery scout** (FR-016 retained) — paid timed search that can **add** at most one seated prospect under free capacity + weekly **signing** counter; generation uses the same V2 rules as Monday intake.

Deprecate shortlist UX that shows exact Deep POT on three fully generated card blobs as the primary “scout” story. Reuse `scouting_reports` shape where practical (tier, timer, expires) or add `academy_scout_assessments` keyed by `card_id` — prefer a dedicated assessment table/columns to avoid conflating shortlist JSON with range math (ponytail: assessment columns on card + small `academy_scout_jobs` for in-flight timers if club-level timer columns are insufficient for per-prospect concurrency).

**Rationale**: Spec US-3 is unambiguously per-prospect range narrowing; FR-016 and entity origins still require a paid acquisition path. Keeping only shortlist fails US-3; assessment-only fails FR-016 edge case “paid scouting and free intake compete for last seat.”

**Alternatives considered**:
- Assessment only — drops paid signing.
- Shortlist only with fogged POT display — still generates three full cards and trains managers on “pick one identity,” not “learn my kid.”
- Exact POT at Deep as reward — forbidden as default by FR-010.

---

## R4 — Visible range initialization and stars

**Decision**: On seat (intake/discovery/cutover), initialize `pot_visible_lo/hi` from academy-level **initial range width** such that `lo ≤ potential ≤ hi`, bounds within rarity ceiling, and UI stars/outlook use a representative value from the **visible interval** (e.g. midpoint or conservative band mapper), never hidden exact POT.

**Rationale**: FR-008, US-8 cutover init, SC-004.

**Alternatives considered**:
- Hide POT entirely until Deep — weaker than progressive narrowing fantasy.
- Show exact POT in list “for power users” — fails product invariant.

---

## R5 — Weekly actions ledger

**Decision**: Persist per-owner UTC-week counters for **promotions** (default max 2) and **paid discovery signings** (configurable; shares retention intent with promotions per FR-016). Enforce inside `promote_academy_player` and discovery-sign RPCs. Optional promote fee (default 500; first free if config) still increments promote counter.

**Rationale**: FR-013 / FR-016 / SC-006; app-only counters lose double-tap races.

**Alternatives considered**:
- Single combined “academy actions” budget — simpler but muddies copy (“was that a promote or a sign?”).
- No paid signing cap — paid scout bypasses retention.

---

## R6 — Trust boundary (FR-022)

**Decision**: Keep Python generators for card identity (names/stats) in the Monday job / discovery finalize path, but RPCs **must** re-validate rarity, OVR, potential against `assert_card_potential_integrity`, band tables, and YA level Legendary rules — **reject** (not silent rewrite of rarity) illegal payloads. Prefer server-assigned bounds/assessment fields over client-supplied ranges.

**Rationale**: Full SQL `create_player_card` is a large rewrite; silent clamp of client rarity would hide cheats. Reject-closed matches Feature 049 ingress posture.

**Alternatives considered**:
- Trust bot JSON — fails FR-022.
- Immediate full SQL factory — correct but outsized for this redesign.

**Upgrade path** (`ponytail:`): move seed-based server generation into RPC later if adversarial trust becomes real.

---

## R7 — Aging / age-out

**Decision**: Replace growth-job “age ≥20 → try promote else delete” with: warning age (config, default 20) → season aging may apply **≤1 POT decay** (never below OVR, never above rarity cap) → age-out boundary (default 21) sets pending + grace → expiry **auto-release** (not forced senior, not silent hard-delete without manager-visible state).

**Rationale**: US-6 / FR-017. Forced promote inflates rosters; silent delete fails “without notice.”

**Alternatives considered**:
- Keep promote-or-delete — rejected by spec.
- Auto-promote always — senior inflation / soft-cap fights.

Hook decay into existing `process_season_aging` or academy growth job with clear idempotent markers — prefer season aging for “per season” semantics; grace cleanup can ride daily growth job.

---

## R8 — Hub entry migration

**Decision**: Primary = `/development` Youth Academy button → shared `show_academy_hub(..., origin=...)`. Optional `/squad` Youth. Keep `/profile` Manage Academy as compatibility. Store facilities remain upgrade-only with richer preview. No `/academy`.

**Rationale**: FR-018 / SC-008; matches existing hub conventions (`/development` progression, `/store` facilities).

---

## R9 — Feature flag and migration numbering

**Decision**: Single forward migration **095** shipping columns, config, RPC rewrites, cutover SQL (repair + range init + grandfather), RLS/guards, and `youth_academy_v2_enabled` (or equivalent). Bot generation/UI V2 paths gate on flag; when off, retain 015 seating behavior only as emergency rollback (document that rollback still leaves repaired POT — irreversible integrity fix is OK).

**Rationale**: Repo head is 094; AGENTS.md forbids editing applied migrations in place. Optional 096 only if VALIDATE CHECKs must wait on a long repair window (unlikely if academy-only repair is small).

**Alternatives considered**:
- Shadow flag forever — YAGNI; ship kill switch for Legendary only long-term.
- Multiple migrations for every sub-feature — slows verify loop; prefer one coherent 095 unless repair blocked.

---

## R10 — Monitoring

**Decision**: Structured logs + optional aggregate columns/metrics from intake/discovery RPCs: generation counts by rarity×YA level, promote/release counts, Legendary count, capacity-block count, academy-origin market listings later. Legendary kill switch = `game_config` weight 0 / boolean — no deploy required.

**Rationale**: FR-024 / SC-007. Full dashboard out of scope (YAGNI) — logs + SQL views/scripts suffice.

---

## Resolved Technical Context checklist

| Item | Resolution |
|------|------------|
| Language / stack | Python 3.11+, Supabase Postgres, discord.py — locked |
| Storage | Extend `player_cards` + weekly ledger + scout assessment jobs; no second inventory |
| Testing | pytest pure math + RPC smoke + schema verify |
| NEEDS CLARIFICATION | None remaining |
