# Research: Fatigue, Injury & Hospital

Phases 1–2 decisions (R1–R9) are locked and shipped. Phase 3 decisions: **R10–R15**.


## R1 — Where fatigue lives

**Decision**: Persist fatigue on `player_cards.fatigue` (0–100, default 100). Never on `players` (club row).

**Rationale**: Cards are the match participants; clubs already own `action_energy` / coins / YA / TG. GDD’s `players.fatigue` was an architectural hallucination corrected in the integration audit.

**Alternatives considered**:
- Club-level fatigue pool — rejected (kills rotation fantasy; conflates with energy).
- Ephemeral in-match-only fitness — rejected (spec requires visible multi-match fatigue).

## R2 — Energy vs fatigue

**Decision**: Orthogonal resources. Matches still spend `action_energy`; fatigue drain/recovery never calls `purchase_energy_refill` or mutates `action_energy`.

**Rationale**: Spec FR-005 / SC-007; existing economy v2 must not regress.

**Alternatives considered**: Spending energy to restore fatigue — rejected for v1 (new sink complexity; not requested).

## R3 — Hospital as third facility

**Decision**: `players.hospital_level` 0–5 (default 0 = 1 bed first-aid). Upgrade via extended `upgrade_club_facility(..., 'hospital')` using `game_config.hospital_upgrade_costs` = `[1500, 4000, 10000, 25000, 60000]`. Share `facility_last_upgrade_at` weekly cap with YA/TG. Instant level (no build timer). UI under `/store` → Club Facilities.

**Rationale**: Q1=A; matches existing facility UX; weekly cap is the anti-inflation lever; GDD 100k–4M detached from ~200 coin match wins.

**Alternatives considered**:
- GDD 100k–4M prestige ladder — rejected (Q1).
- New `/hospital` command — rejected (AGENTS scope / YAGNI).
- Multi-day build timers — deferred (Ponytail; YA/TG have none).

## R4 — Injury authority without live pause

**Decision**: Phases 1–2 authoritative injuries are **post-match rolls** (fatigue/age/PHY formulas) written via `process_post_match_injuries`. Soft-cap **A+C**: only `fatigue < 75` eligible; max **one** injury per club per match (first successful roll in starter order). Mid-match NSS cosmetic `INJURY` events remain non-authoritative flavor until Phase 3 (see R12 — Phase 3 makes mid-match rolls authoritative and skips the second post-match roll when recordings exist).

**Rationale**: Q3=A defers stream pause; A+C keeps injuries a rotation consequence, not a squad wipe; FR-015 satisfied by post-match persistence.

**Alternatives considered**:
- Force mid-match pause in first ship — rejected (Q3).
- Soft-cap A only or B (lower base %) — superseded by product lock **A+C**.
- Remove all INJURY commentary — optional; keeping flavor is fine if copy does not claim persistence.

## R5 — Tier 4 / career-ending

**Decision**: v1 tier weights map roll 100 → **Major**. No auto-retire. Schema may still allow `injury_tier` 1–3 only (or 1–4 reserved unused).

**Rationale**: Q2=A — Discord rage-quit risk; progression destruction disproportionate to 1% RNG.

**Alternatives considered**: Auto-retire; manager choice retire vs permanent OVR cut — both deferred.

## R6 — Match engine integration (Phases 1–2)

**Decision**: Apply fatigue penalties in `phase_stats.phase_stat_value` by multiplying the **phase attribute** portion before the 70/30 zone blend. Hydrate `MatchPlayerCard.fatigue` from DB in `card_from_db_row`. Do **not** implement `generator.send()` or Discord wait loops in this plan.

**Rationale**: GDD math target; live path is NSS + `async for`; tactics already mutate `MatchState` without send().

**Alternatives considered**:
- Switch Discord to legacy interval engine — rejected (large regression).
- Post-process ratings only — rejected (fatigue should affect live sim outcomes).

## R7 — Post-match pipeline order

**Decision**: After match ends: (1) `apply_match_economy`, (2) `process_match_result` / XP, (3) `apply_match_fatigue`, (4) `process_post_match_injuries` (Phase 2). Friendlies skip 1–4 for fatigue/injury (and already skip economy/XP).

**Rationale**: Preserve existing reward idempotency; fatigue/injury are additional batch steps; failures should surface without claiming full success.

**Alternatives considered**: Bundling into `process_match_result` — possible later; separate RPCs keep blast radius small for first ship.

## R8 — Recovery scheduling

**Decision**: Add APScheduler job calling `process_daily_recovery()` (suggest daily ~00:05 UTC, separate from Monday aging). Optionally also expose lazy sync on profile/squad open for fatigue display freshness — not required if daily job is reliable.

**Rationale**: Constitution V; aging is weekly and must not be overloaded; energy stays lazy.

**Alternatives considered**: Only lazy recovery on every command — harder to reason about injury day clocks; daily batch is clearer for discharge dates.

## R9 — Overflow UX when hospital full

**Decision**: RPC returns `overflow` list; bot attempts DM with discharge/leave-untreated select; if DMs fail, Hospital panel under Club Facilities shows waiting injured (in_hospital=false) with same actions. Never silent.

**Rationale**: Spec SC-005; mirrors claim-rewards DM fallback pattern.

## R10 — Phase 3 boundary (updated 2026-07-11)

**Decision**: Phases 1–2 shipped without interactive pause. Phase 3 is now planned in [plan-phase3.md](./plan-phase3.md) and [contracts/in-match-injury-sub.md](./contracts/in-match-injury-sub.md). Implementation still a separate PR after `/speckit.tasks` for Phase 3 only.

**Rationale**: Q3=A isolated Discord risk; Phases 1–2 stable enough to plan the pause UI.

## R11 — Phase 3 pause mechanism (2026-07-11)

**Decision**: Pause by **stopping the Discord `async for` advancement** and awaiting an `asyncio.Event` (≤30s). Manager choice mutates `MatchState` / squad lists like `TouchlineView` mutates `home_tactics_modifier`. **Never** use `generator.send()` / `asend()`.

**Rationale**: Live path is async generator consumed with `async for`; send protocol is unused and would require rewriting `stream_match`.

**Alternatives considered**: Threading the generator with send — rejected; pre-sim entire match then fake pause — rejected (breaks live commentary).

## R12 — Authoritative injury source in Phase 3

**Decision**: Mid-match A+C rolls (fatigue &lt; 75, max one *prompt chain* per stoppage queue item, still max meaningful injuries via sequential queue) drive sim + `recorded_injuries`. Post-match **persists recordings** and skips a second `select_post_match_injury` when recordings exist.

**Rationale**: Avoid double injury tax; FR-015 (no fake ticker-only injuries).

## R13 — Stoppage definition without DEAD_BALL

**Decision**: Interactive yield only on/after `FOUL`, `GOAL`, `SAVE`, `HALF_TIME`, or set-piece resolution when `pending_injuries` non-empty. Open-play rolls set pending and continue until stoppage.

**Rationale**: NSS phases lack dead-ball; these events are the closest natural breaks already yielded to Discord.

## R14 — Auto-sim / AI

**Decision**: No Discord wait. Call pure `auto_resolve_injury(...)` immediately inside the consumer or inside `collect_match_events` wrapper.

**Rationale**: SC-009 / league silent path must not hang.

## R15 — Scope freeze for Phase 3 PR

**Decision**: No Hospital cost changes, no new slash commands, no friendlies, no Tier-4 retire, no build timers.

**Rationale**: Ponytail; isolate Discord risk.
