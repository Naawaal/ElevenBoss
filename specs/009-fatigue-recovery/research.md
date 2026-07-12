# Research: Active Fatigue Recovery

**Feature**: `009-fatigue-recovery` | **Date**: 2026-07-12  
**Purpose**: Resolve technical unknowns before implementation; map EA FC / FM inspiration onto ElevenBoss without inventing unused infrastructure.

---

## R1 — Recovery Session timing (async vs instant)

**Decision**: Recovery Sessions are **instant**, same UX as skill drills (`process_stat_drill` completes in one RPC). Do **not** build a 4-hour async job queue or a `player_drills` table.

**Rationale**:
- Spec FR-004 assumed “~4 hours like a normal drill.” Codebase audit shows Development drills are **synchronous**: one `process_stat_drill` call debits energy/coins, grants XP, returns immediately. There is no `player_drills` table and no drill completion sweeper.
- Building async Recovery-only timers would add tables, schedulers, cancel/injury race logic, and a UX that differs from every other Development action — violates constitution YAGNI and AGENTS ponytail rules.
- Agency (fitness vs XP) and capacity opportunity cost still hold with instant sessions.

**Alternatives considered**:
| Option | Rejected because |
|--------|------------------|
| 4-hour async job + new table | Spec assumption was wrong about existing infra; large surface for one feature |
| Soft “cooldown” on the card without a job | Extra state; managers already have daily drill caps |
| Keep wording “4 hours” in UI while completing instantly | Dishonest UX |

**Spec reconcile on implement**: Update FR-004 / acceptance copy to “completes immediately like skill drills” in `specs/009-fatigue-recovery/spec.md` and `.specify/specs/v1.0.0/`.

---

## R2 — RPC shape (extend drill vs new recovery RPC)

**Decision**: New atomic RPC `process_recovery_session(p_owner_id BIGINT, p_player_card_id UUID) RETURNS JSONB`. Do **not** overload `process_stat_drill` with a `'recovery'` drill id.

**Rationale**:
- `process_stat_drill` is tightly coupled to coin costs, XP via `apply_card_xp`, age multipliers, and TG XP bonus. Branching it for “0 XP / 0 coins / +fatigue” risks regressing skill drills.
- Mentor Transfusion pattern (`transfer_mentor_xp`) already established: separate RPC when the mutation pipe differs.
- Capacity sharing is still explicit: same `daily_drill_count` / `player_drill_daily_log` increments inside the new RPC.

**Alternatives considered**:
| Option | Rejected because |
|--------|------------------|
| `p_drill_id = 'recovery'` in `process_stat_drill` | Muddies XP pipe; harder to guard “no apply_card_xp” |
| Direct cog `UPDATE player_cards.fatigue` | Violates atomic RPC / AGENTS mutation rules |

---

## R3 — Costs, caps, and economy pipe

**Decision**:
- **Coins**: 0 (call `apply_club_economy` with coin delta `0` only if energy debit needs the pipe — prefer single economy call with `coins=0`, `energy=−N`).
- **Energy**: same as Basic skill drill — `get_game_config_int('drill_basic_energy', 10)` (or dedicated `fatigue_recovery_energy` defaulting to 10 for future tuning).
- **Caps**: consume club daily drills (20) and per-card `player_drill_daily_log` (5), identical to skill drills.
- **Economy source string**: `'recovery_session'`.
- **Never** call `apply_card_xp`.

**Rationale**: Spec FR-005/FR-006; prevents free infinite recovery spam while keeping Recovery a strategic capacity spend.

---

## R4 — Training Ground passive formula vs schema

**Decision**: Non-hospital daily passive = `15 + (training_ground_level × 5)`, clamped to 100. Hospital path stays `fatigue_hospital_per_day` (45).

**Schema note**: `players.training_ground_level` is `CHECK (BETWEEN 1 AND 5)` with default **1**. Spec’s “TG level 0 → 15” is **not reachable** in production. Effective table:

| TG level | Passive / day |
|----------|-------------|
| 1 | 20 (matches legacy flat +20) |
| 2 | 25 |
| 3 | 30 |
| 4 | 35 |
| 5 | 40 |

**Implementation**: Replace the single flat `UPDATE` in `process_daily_recovery` with an `UPDATE … FROM players` join so each card uses its owner’s TG level. Seed `game_config` keys `fatigue_passive_base=15`, `fatigue_passive_tg_per_level=5`; stop using flat `fatigue_passive_per_day=20` for the non-hospital path (leave key for rollback/docs or update comment).

**Pure mirror**: `packages/player_engine/fatigue.py` — `passive_recovery_amount(tg_level: int) -> int` and extend `apply_passive_recovery(..., tg_level=1)`.

**Alternatives considered**:
| Option | Rejected because |
|--------|------------------|
| Keep flat 20 + optional TG bonus only for L≥2 | Spec wants explicit base 15 + 5×L |
| Allow TG 0 in schema | Unrelated facility migration; out of scope |

---

## R5 — Industry mapping (EA FC 26 / FM → ElevenBoss)

**Decision**: Map concepts onto existing surfaces only.

| Industry concept | ElevenBoss mapping |
|------------------|-------------------|
| EA FC Recovery training session | Development → Recovery Session (instant) |
| EA FC Training Ground facility recovery | TG-scaled `process_daily_recovery` |
| FM Rest toggle | Recovery Session opportunity cost (uses drill slot) |
| FM sports science / physio staff | Abstracted into TG level (no new staff entity) |
| UT physio consumable | **Out of scope** (Solution C) |

---

## R6 — Injury / evolution / match interactions

**Decision**:
- Reject Recovery if `injury_tier IS NOT NULL` or `in_hospital` (Hospital owns injury recovery).
- Reject if card in active evolution (same as skill drills).
- Reject if `fatigue >= 100` or retired / not owned.
- `assert_not_in_match` before starting.
- Bench rest (+15) and match drain **unchanged**.
- Friendlies: no match fatigue writes (existing); Recovery Session still allowed as Development action.

---

## R7 — UI surface

**Decision**: Extend `/development` → Training Drills flow only. Add a clear **Recovery Session** choice after (or alongside) player select — distinct embed copy: +40 fatigue, 0 XP, energy cost, no coins. No new slash command. No Store button.

**Squad indicator (FR-007 / US-2)**: Instant completion means “in progress” state does not exist. Show success feedback with new fatigue value; optional one-line “Recovered via Recovery Session” on the result embed. Do not invent a persistent “recovering” badge unless a later async design lands.

---

## R8 — Migration / verify / callers

**Decision**: New migration `054_fatigue_recovery.sql` that:
1. Seeds/updates `game_config` for recovery amount + passive base/bonus.
2. `CREATE OR REPLACE process_daily_recovery` with TG join.
3. `CREATE OR REPLACE` / new `process_recovery_session` + GRANTs.
4. Schema guard entries for the new function; extend `verify_required_schema.sql`.

Grep callers of `process_daily_recovery` / `apply_passive_recovery` / Development drill UI before ship. Scheduler job in `scheduler_jobs.py` already calls `process_daily_recovery` — no new APScheduler job.

---

## Resolved clarifications

| Former unknown | Resolution |
|----------------|------------|
| 4-hour async drills | Do not exist → instant Recovery |
| `player_drills` table | Do not create |
| TG level 0 | Unreachable; formula uses 1–5 |
| Physio Store item | Out of scope |
| Share drill caps? | Yes |
| Energy cost | Basic drill energy (default 10) |
