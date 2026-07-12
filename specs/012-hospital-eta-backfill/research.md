# Research: Hospital ETA Backfill

**Feature**: `012-hospital-eta-backfill` | **Date**: 2026-07-12  
**Purpose**: Resolve how to fair-recalc live hospital/overflow state without lengthening clocks or breaking idempotency.

---

## R1 — ETA formula shape (idempotent)

**Decision**: Anchor the candidate return date to **admission + new_total_days**, then take `LEAST(current_expected, candidate)`. Early-discharge when `NOW() >= LEAST(...)`.

Equivalent to the product formula:

```text
days_served = now − admission
remaining   = new_total − days_served
new_eta     = now + remaining   ≡   admission + new_total
```

**Rationale**: Using `now + remaining` alone is fine once, but re-deriving from “days served since last run” without anchoring can drift. Anchoring to admission makes re-runs produce the **same** candidate ETA → `LEAST` is a no-op after the first shorten (SC-004).

**Alternatives considered**:

| Option | Rejected because |
|--------|------------------|
| Always set `now + (new_total − served)` without LEAST | Can lengthen if clock/timezone quirks; fails FR-003 |
| Store a `backfill_applied_at` flag column | Extra schema for a one-shot; YAGNI if formula is idempotent |
| Only shorten if old ETA implies base > 7 Major | Brittle heuristic; formula-based LEAST is cleaner |

---

## R2 — Where mutation lives (SQL RPC vs Python loop)

**Decision**: One Postgres function `backfill_injury_eta_fairness() RETURNS JSONB` in migration `057`, invoked by `scratch/apply_migration_057.py` (and safe to re-invoke). Do **not** loop UPDATEs from a Discord cog.

**Rationale**: AGENTS Database Rule + atomic batch; small N but still one transaction; returns structured summary for DM script.

**Alternatives considered**:

| Option | Rejected because |
|--------|------------------|
| Pure Python psycopg row loop | More round-trips; easier to half-apply |
| Silent DO $$ only at migrate time | Harder to re-run / inspect summary; RPC is clearer |

---

## R3 — Early discharge end-state

**Decision**: Mirror **successful Hospital recovery** in `process_daily_recovery` (not manual `discharge_from_hospital`, which leaves the card injured untreated):

- Set `hospital_patients.discharge_date = NOW()`
- Clear card: `injury_tier NULL`, `injury_started_at NULL`, `injury_recovery_days 0`, `in_hospital FALSE`
- `fatigue = LEAST(100, fatigue + 25)` (existing hospital-completion bump)

**Rationale**: Spec Assumptions: recovered, not “kicked to untreated.” Manual discharge UX is a different path.

---

## R4 — `new_total_days` continuous vs ceil

**Decision**: Use the **same integer CEIL** as live admits:  
`CEIL(base::numeric / (1 + 0.2 * hospital_level))` with bases 1/4/7, then add that many days to `admission_date`.

**Rationale**: Managers must not see backfilled ETAs that disagree with what a fresh admit of the same tier/Hospital would get. Fractional **elapsed** time is still honored because discharge checks `NOW() >= final_eta` (mid-day returns allowed).

---

## R5 — Overflow untreated

**Decision**: Include in the same RPC.

```text
elapsed = (NOW() − injury_started_at) in days  (0 if null)
raw     = new_base(tier) − elapsed
remain  = max(0, ceil(raw))           # whole days left for daily ticker
final   = min(injury_recovery_days, remain)   # never lengthen remaining
if final = 0 → clear injury (no hospital row)
else UPDATE injury_recovery_days = final
```

**Rationale**: Spec US3 / FR-007; daily job already decrements untreated by 1/day.

---

## R6 — Notifications

**Decision**: RPC returns `early_discharged: [{owner_id, player_card_id, name, tier}, ...]`. A **separate** scratch/bot helper sends best-effort DMs after commit. SQL must not call Discord.

**Rationale**: FR-008; packages/SQL cannot import discord; DM failure must not undo data (already committed).

**Copy** (player-facing): Medical Update — player(s) discharged early due to updated medical protocols; check `/profile` → Manage Hospital.

---

## R7 — Dependency on 011

**Decision**: Guard at start of RPC: assert `get_game_config` / known bases path is post-056 (e.g. document prerequisite; optional assert that CASE in `admit_to_hospital` isn’t required if we hardcode 1/4/7 in the backfill to match 011).

Backfill embeds bases **1/4/7** explicitly (same as 056) so it does not re-read old CASE from historical migration files.

---

## Spec reconcile on implement

- `.specify/specs/v1.0.0/spec.md`: note mid-injury fairness pass (012) after AC-39i.
- `change_log.md`: short note that existing Hospital stays were recalculated fairly.
- Feature 011 Assumptions “forward-only default” superseded for open stays by 012.
