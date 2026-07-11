# Implementation Plan: Profile Finance & Hospital Hub

**Branch**: `003-profile-finance-hospital` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-profile-finance-hospital/spec.md`

## Summary

Turn `/profile` into a **one-stop club dashboard**: keep existing identity / energy / division / record / trophies, add a scannable **Club Finance** + **Hospital** summary, and attach a three-button hub (**Manage Hospital**, **Finances**, **View Club Stats**) that reuses Store hospital management, club-finances detail, and the Squad hub.

**Technical approach**: Extract `show_profile` + `ProfileHubView` (same hub pattern as Store/Development). Compose dashboard fields via a small profile embed helper. Parameterize `show_hospital_panel` / `HospitalPanelView` with `origin=("facilities"|"profile")` and add a Hospital upgrade control on that panel so Manage Hospital is not a dead end at L0. Extract finance embed builder for shared use by `/club-finances` + profile Finances sub-view. Extract `show_squad_hub` for Club Stats. **No new slash commands, tables, or RPCs** — read existing `players` + `hospital_patients` only.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, supabase async ≥2.0, pydantic ≥2.0, local `economy` (`facility_effects` hospital helpers)

**Storage**: Existing Supabase schema from migration `050` — `players.coins`, `players.tokens`, `players.hospital_level`, `hospital_patients` (+ joined `player_cards`). No new migration for this feature.

**Testing**: pytest for pure summary formatters (hospital section copy / truncation); Discord flows via [quickstart.md](./quickstart.md)

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — `apps/discord_bot` UI hub only (no package math changes)

**Performance Goals**: Profile load stays within deferred followup window; ≤2–3 DB round-trips (player row, patients join, optional history already present); no per-patient mutation loops

**Constraints**: AGENTS.md — no `discord` in `packages/`; no new slash commands; coins only via existing RPCs on upgrade; defer immediately; soft-keep `/club-finances`; Store → Facilities → Hospital path must keep working; SDD reconcile `.specify/specs/v1.0.0/` on implement

**Scale/Scope**: Presentation + navigation hub; ~8–12 files; depends on `002-injury-fatigue-hospital` hospital UI already present

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | All UI in `apps/discord_bot`; reuse `economy.facility_effects` (already pure) |
| II. DB mutations via RPC / atomic paths | PASS | Profile is read-only; upgrades/admit/discharge keep existing RPCs |
| III. Typing / Pydantic at boundaries | PASS | Type-hint new `show_*` helpers; no new cross-package models required |
| IV. Slash + defer | PASS | Extend existing `/profile`; keep `guild_only` + defer; no new commands |
| V. APScheduler | PASS | No new jobs |
| VI. User-friendly errors | PASS | Partial hospital failure → section fallback; stale views → re-run `/profile` |
| VII. YAGNI | PASS | No ledger, no `/hospital`, no schema; reuse hospital panel + finances embed |

**Post-Phase 1 re-check**: PASS — design adds hub wiring only; hospital math and Store entry remain owned by 002.

## Project Structure

### Documentation (this feature)

```text
specs/003-profile-finance-hospital/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1 (read-model / view entities)
├── quickstart.md        # Phase 1
├── contracts/
│   ├── profile-dashboard.md
│   ├── profile-hospital-nav.md
│   └── club-finances-soft-deprecate.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
apps/discord_bot/
├── cogs/
│   ├── profile_cog.py           # MODIFY — show_profile + ProfileHubView; command calls show_profile
│   ├── economy_cog.py           # MODIFY — extract finance embed/panel; /club-finances pointer footer
│   └── squad_cog.py             # MODIFY — extract show_squad_hub for profile Club Stats button
├── views/
│   └── store_facilities.py      # MODIFY — origin=profile|facilities; Back routing; hospital upgrade on panel
├── embeds/
│   ├── hospital_embeds.py       # REUSE — panel embed; share ETA helper if needed
│   └── profile_embeds.py        # NEW (optional but preferred) — dashboard finance/hospital field builders
tests/
└── test_profile_hospital_summary.py   # NEW — truncation / L0 empty-state / bed copy formatters
change_log.md                            # MODIFY — player-facing hub note on ship
.specify/specs/v1.0.0/spec.md + plan.md  # RECONCILE on implement
```

**Structure Decision**: Stay inside existing Discord hub layout. Prefer extracting `show_*` module-level functions (Store/Development pattern) over stuffing navigation into the slash handler. Lazy-import cross-cog `show_*` in button callbacks to avoid import cycles.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Notes (for `/speckit.tasks`)

1. **`show_profile(interaction, owner_id)`** — single refresh entry used by `/profile` and all **Back to Profile** paths; always re-fetch player + active patients.
2. **`ProfileHubView`** — timeout aligned with other hubs (~180–900s); `interaction_check` owner-only; buttons: Manage Hospital → `show_hospital_panel(..., origin="profile")`; Finances → finance panel with Back → `show_profile`; Club Stats → `show_squad_hub` (edit same message; include pitch attachment).
3. **Hospital `origin`** — `facilities` keeps Back → `show_facilities`; `profile` Back → `show_profile`. Add **Upgrade Hospital** on `HospitalPanelView` (calls existing `upgrade_club_facility` path used by Facilities) so L0 Manage Hospital is not a dead end.
4. **L0 copy** — Profile summary uses “No Hospital – build one in the Store!” per FR-004; panel still shows L0 + 1 bed math from 002 (`beds = level + 1`).
5. **Queries** — `players` by `discord_id`; `hospital_patients` where `owner_id` and `discharge_date IS NULL` with `player_cards(name, …)`; finance panel also loads `squad_assignments` → starting XI for wages (same as today).
6. **Soft-deprecate** — `/club-finances` unchanged functionally; footer/description adds “Unified dashboard: `/profile`”.
7. **Keep** `@app_commands.guild_only()` on `/profile` (DM blocked by Discord — clear platform error; no custom DM path in v1).
