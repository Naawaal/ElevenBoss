# Research: Autonomous League Administration Policy

**Feature**: `027-league-autonomous-admin`  
**Date**: 2026-07-21

## R1 — Discord surface: League Time only

**Decision**: Remove `/admin → League Management` as a lifecycle/competitive control surface. Add `/admin → Server Settings → League Time` with IANA timezone + local resolution hour + preview. Keep existing `/admin → Announcements` for announce channel/role (presentation only — not lifecycle authority).

**Rationale**: Spec FR-005/FR-011 require a single league schedule preference UI and forbid Discord lifecycle mutation. Announcements already exist as a separate hub branch and do not advance competitive state.

**Alternatives considered**:
- Reduce League Management to timezone-only button — rejected; keeps a “management” mental model and duplicates the specified Server Settings path.
- Move announce channel into League Time — rejected; conflates schedule preference with presentation routing; out of scope.

## R2 — Defaults: UTC + 00:00, non-blocking

**Decision**: When `guild_config.league_timezone` or `league_resolution_hour_local` is NULL, preparation and schedule generation **coalesce** to `UTC` and hour `0`. Do not block season start awaiting admin configuration. Optional non-blocking admin notice may be enqueued via outbox later; V1 may log-only.

**Rationale**: Spec FR-012/FR-013. Current engine raises if TZ/hour unset and UI/modal defaults hour to `20` / `game_config` seed `league_lifecycle_default_resolution_hour=20`, which conflicts with 027.

**Alternatives considered**:
- Keep default hour `20` for “evening match” UX — rejected; 027 explicitly freezes `00:00` as the unconfigured default; configured guilds still choose evening hours via League Time.
- Write UTC/0 into every guild_config row on migrate — unnecessary; coalesce at read/prepare is enough and preserves “unconfigured” detection for optional notices.

## R3 — Active season freeze vs guild preference

**Decision**: Reaffirm `026` behavior: at preparation, copy TZ + hour into `league_seasons.timezone`, `resolution_hour_local`, `ruleset_snapshot`, and precomputed `league_matchdays` / fixture windows. Guild League Time upserts never UPDATE those season/matchday columns.

**Rationale**: Spec FR-009/FR-010/SC-003. Already largely implemented; plan must not regress.

**Alternatives considered**: Live-rebase active season on TZ change — rejected (Dynamics-style rigidity and fairness issues).

## R4 — Remove Discord lifecycle mutators (including pause / force-end)

**Decision**: Delete Discord handlers/buttons for: open/close registration, start season, configure season duration/fees/size/prizes, kick, force-sim, pause/resume, force-end, run cycle now, and Lifecycle V1 cutover toggle in the TZ modal. Cutover remains **global `game_config` + operator/DB only** (exclusive per-guild flag may stay as a column but is not Discord-editable).

**Rationale**: Spec FR-004/FR-015. Current automation-on path still shows Pause, Force End, Timezone(+cutover), Run Cycle — violates 027.

**Alternatives considered**:
- Hide buttons when automation on but keep code paths — rejected; dead Discord paths invite re-wiring and fail SC-002 inventory.
- Keep Force End as Discord break-glass — rejected; recovery must be operator/internal.

## R5 — Operator recovery minimum

**Decision**: Ship a trusted `scripts/league_lifecycle_recover.py` (service credentials) that: (1) recovers stalled operations, (2) calls `process_due_transitions`, (3) drains/publishes outbox — all through existing engine/recovery modules. Also call stalled recovery from the regular wake job (not startup-only). On retry exhaustion, emit structured ERROR logs (alert hook can be ops-side); no Discord admin UI.

**Rationale**: Spec FR-016–FR-018 and edge-case “recovery mandatory after removing manual controls.” No CLI exists today.

**Alternatives considered**:
- Full operator web console — YAGNI for V1.
- Discord owner-only secret command — still Discord; violates FR-015 spirit and SC-002.
- DB-only manual row edits — forbidden; bypasses rulebook.

## R6 — Pause / cancel after Discord removal

**Decision**: Discord never exposes pause/cancel. Engine methods may remain for **operator script** use only if explicitly invoked with an operation key + journal write. Happy-path autonomy does not require pause. Prefer documenting operator “retry wake” first; add operator pause/cancel flags to the CLI only if ops proves need (still same engine).

**Rationale**: Spec assumption: pause/cancel if retained are operator-only via shared engine. Avoid shipping Discord-equivalent flags under a new name.

**Alternatives considered**: Delete pause from engine entirely — deferred; `026` still defines pause rebase math; removing state machine support is a larger rulebook change than 027’s Discord policy.

## R7 — IANA validation

**Decision**: Validate with `zoneinfo.ZoneInfo(name)`; reject strings matching raw offset patterns (`UTC+…`, `GMT-…`, numeric offsets) even if some platforms accept them. Preview computes “next/current local resolution → UTC” for display using stdlib.

**Rationale**: Spec FR-008; `Asia/Kathmandu` and DST-safe zones require IANA identity.

**Alternatives considered**: Allow fixed offsets — rejected by spec.

## R8 — Schema / migration

**Decision**: Prefer **no competitive schema change**. Optional `072_league_time_defaults.sql` only to align `game_config.league_lifecycle_default_resolution_hour` to `0` and extend verify script if a new RPC appears (none required for coalesce-in-app). League Time continues as direct `guild_config` upsert (single row) — acceptable; not a multi-step financial mutation.

**Rationale**: Columns already exist in `070`. Ponytail — don’t migrate for coalesce logic alone.

**Alternatives considered**: New `set_league_time` RPC — optional nicety; not required for correctness.

## R9 — Relationship to 026 docs

**Decision**: Amend `specs/026-league-lifecycle-rulebook/contracts/admin-and-hub-surfaces.md` (and any FR notes that mandate Discord pause/force-end) so 026 no longer contradicts 027. Competitive rulebook in 026 remains authoritative for calendar/match/promo.

**Rationale**: Single source of truth; implementers will otherwise reintroduce banned controls.

## Resolved clarifications

| Topic | Resolution |
|-------|------------|
| Unconfigured default hour | `00:00` (027 wins over prior `20` seed/UI) |
| Announcements channel/role | Stay under Announcements; not League Time |
| Cutover toggle | Not Discord-editable |
| Operator tool shape | CLI script + wake stalled recovery; no portal |
| Pause after Discord strip | Engine may retain; Discord removed; CLI pause optional later |
