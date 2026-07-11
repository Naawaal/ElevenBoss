# Research: Profile Finance & Hospital Hub

**Feature**: `003-profile-finance-hospital` | **Date**: 2026-07-11

## R1 — Hub pattern for `/profile`

**Decision**: Extract module-level `show_profile(interaction, owner_id)` and attach `ProfileHubView`, matching Store (`show_store` / `StoreHubView`) and Development (`show_hub`).

**Rationale**: Spec requires refresh after hospital actions and Back-from-subview. A single `show_*` entry is the established ElevenBoss pattern and avoids duplicating fetch/embed logic in the slash handler and every button.

**Alternatives considered**:
- Keep all logic inside `ProfileCog.profile` only — breaks Back/refresh without awkward cog method binding.
- Persistent `custom_id` views registered in `main.py` — unnecessary for ephemeral personal hubs; timeout + “re-run `/profile`” is enough (FR stale-view edge case).

## R2 — Hospital panel reuse vs duplicate UI

**Decision**: Reuse `show_hospital_panel` / `HospitalPanelView` / `hospital_panel_embed`. Add `origin: Literal["facilities", "profile"]` (default `"facilities"`) so Back returns to the correct parent. Add an **Upgrade Hospital** control on the hospital panel (today upgrade lives only on `FacilitiesHubView`).

**Rationale**: FR-006 requires upgrade + admit/discharge from Manage Hospital without forcing `/store` first. Current panel has admit/discharge but no upgrade — that gap would make L0 Manage Hospital a dead end. Parameterized origin preserves FR-014 (Store path unchanged).

**Alternatives considered**:
- Profile → `show_facilities` with back-to-profile — works but dumps YA/TG UI when the manager asked for Hospital.
- Fork a second `ProfileHospitalView` — YAGNI; doubles admit/discharge bugs.
- Ephemeral followup for hospital (leave profile message stale) — fails FR-009 refresh expectation.

## R3 — Hospital level 0 messaging vs bed formula

**Decision**: On the **profile summary**, treat `hospital_level == 0` as the FR-004 empty state (“No Hospital – build one in the Store!”) and do **not** show `1/1 beds` there. The **hospital panel** continues to use `hospital_bed_capacity(level) = level + 1` from 002 (L0 still has 1 bed for auto-admit math).

**Rationale**: Spec UX wants a clear “not built” call-to-action. Changing bed math would rebalance 002; presentation-only empty state is safer.

**Alternatives considered**:
- Show L0 as “Level 0 · Beds 0/1” on profile — confuses “not built” with capacity.
- Change `hospital_bed_capacity(0)` to 0 — breaks 002 auto-admit / contract tables.

## R4 — Finances button depth (v1)

**Decision**: Extract today’s `/club-finances` embed builder into a shared helper/panel with **Back to Profile**. No `economy_ledger` browser in v1. Soft-deprecate slash via footer pointer to `/profile`.

**Rationale**: Matches FR-007 / Out of Scope. Reuse avoids drift between slash and button.

**Alternatives considered**:
- Ledger from `economy_ledger` — explicitly out of scope.
- Hard-remove `/club-finances` — breaks muscle memory (spec P3 soft transition).

## R5 — View Club Stats target

**Decision**: Route to Squad hub via extracted `show_squad_hub(interaction, owner_id)` (edit current message + pitch attachment). Not `/development`.

**Rationale**: Spec assumption + FR-008. Squad is the club roster/stats surface; Development is progression drills/fusion.

**Alternatives considered**:
- Followup “open `/squad`” text only — weaker one-stop UX.
- Development hub — wrong domain for “club stats”.

## R6 — DM / no-club behavior

**Decision**: Keep `@app_commands.guild_only()` and `@ensure_registered` on `/profile`. No custom DM dashboard in v1.

**Rationale**: Current command already guild-only; Discord rejects DMs before handler runs. `ensure_registered` covers no-club. Satisfies FR-010 with platform/middleware messages rather than new branches.

**Alternatives considered**:
- Remove `guild_only` to show club in DMs — possible later; not required for v1 and changes product policy.

## R7 — Schema / migrations

**Decision**: **No new migration.** Read `players` + active `hospital_patients` (+ card join). Mutations only through existing `upgrade_club_facility` / `admit_to_hospital` / `discharge_from_hospital`.

**Rationale**: Spec assumption — presentation hub only. Migration 050 already defines hospital columns/table/RPCs.

## R8 — Embed composition & truncation

**Decision**: Prefer `embeds/profile_embeds.py` (or helpers beside `profile_cog`) for Finance + Hospital summary fields. Cap patient lines (~5) with “and N more — open Manage Hospital”. Reuse hospital ETA formatting style from `hospital_embeds._eta_str` (export/share small helper to avoid drift).

**Rationale**: Keeps cog thin; FR-011 size safety; consistent recovery date copy.

## R9 — Cross-cog imports

**Decision**: Lazy-import `show_profile` / `show_hospital_panel` / `show_squad_hub` inside button callbacks (same pattern as `store_facilities` → `show_store`).

**Rationale**: Prevents circular imports between `profile_cog`, `store_facilities`, `squad_cog`, `economy_cog`.

## R10 — Agent context script

**Decision**: Skip — repo has no `.specify` agent-context updater script (only `setup-plan.ps1` / `setup-tasks.ps1` / etc.).

**Rationale**: Plan agent step is N/A when the tool is absent; feature docs under `specs/003-…` are sufficient.
