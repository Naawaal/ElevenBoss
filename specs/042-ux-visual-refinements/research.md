# Research: Store / Swap / Hospital UX Refinements

**Feature**: `042-ux-visual-refinements` | **Date**: 2026-07-23

## R1 — Energy near-full threshold & Store wiring

**Decision**: Implement pure helper `is_energy_near_full(current, maximum) -> bool` and `near_full_reason(current, maximum) -> Literal["full","near",None]` in `packages/energy/`. Near-full when `maximum > 0` and (`current >= maximum` → `"full"`; else `current >= ceil(0.95 * maximum)` **or** `current >= maximum - 5` → `"near"`; else `None`). Wire in `show_store` after `sync_action_energy` (already loads `ae`/`max_e`); pass into `StoreHubView._sync_button_states`. Disable `store_energy_refill`, set label to `⚡ Energy already full` or `⚡ Near maximum`, and add/adjust Energy Refill embed field copy. Fail-open if `max_e` missing/≤0.

**Rationale**: Spec FR-002; Store already syncs energy every open/refresh; mirrors daily-login/gacha disable pattern. Pure package keeps pytest free of Discord.

**Alternatives considered**:
- Disable only at exact max → rejected (wastes coins when +50 would mostly clip).
- Hardcode max=120 in cog → rejected (clubs may have different `max_energy`).
- Server-side RPC reject only → rejected (spec wants proactive disabled control).

## R2 — Discord “tooltip” for disabled refill

**Decision**: No native Discord button tooltips. Use **disabled button label** (≤80 chars) plus embed field line under Energy Refill. Prefer accurate full vs near label on the button when both fit.

**Rationale**: Matches existing store UX (gacha cooldown is embed + disabled button). Spec Assumptions already allow label/field substitute.

**Alternatives considered**: Modal on click → rejected (extra tap, violates SC-002 spirit for enabled path and confuses disabled path). Ephemeral followup on click → impossible when button disabled.

## R3 — Swap visual style

**Decision**: **Side-by-side comparison cards** (v1), not pitch highlight. New `generate_swap_compare_image(out_card|None, in_card|None) -> discord.File` reusing roster-card styling from `pitch_generator._render_roster_grid` (OVR, position, name, rarity border; show PAC/SHO/PAS/DRI/DEF/PHY if present on card dict). Placeholders for unselected sides (“Select starter…” / “Select reserve…”). On `SquadSwapView` open and each select callback, `edit_message(..., attachments=[compare_file])`. Keep dual selects + Confirm gating unchanged.

**Rationale**: Spec default; swap already text-select based; full pitch already used on squad hub—comparison cards answer “who am I swapping?” faster. Attribute rows need only fields already on starter/reserve dicts from squad fetch (extend select payload if attrs missing).

**Alternatives considered**:
- Pitch slot highlight → deferred; heavier and overlaps hub pitch.
- Replace selects with image buttons → YAGNI; Discord select limit/UX worse for 11+ bench.
- Static embed fields only → fails FR-006 visual requirement.

## R4 — Hospital asset & dynamic overlay

**Decision**: Use `assets/admited.png` (1536×1024 RGB clipboard/list board with ~5–6 lined rows and teal bullets) as base. `generate_hospital_board(patients: list[dict]) -> discord.File | None` draws name (+ optional short severity/ETA) on successive row baselines (tunable Y constants as % of height). Cap overlays at **6** rows (matches L5 bed capacity `level+1`). Overflow remains in embed “Current Patients” text. Empty list still returns the empty board image (no names). If file missing/unreadable → return `None`; `show_hospital_panel` skips attachment and keeps text-only embed (FR-014). `hospital_panel_embed` calls `embed.set_image(url="attachment://hospital_board.png")` when file present. Regenerate on every `show_hospital_panel` (admit/discharge/upgrade already refresh the panel).

**Rationale**: Asset is a patient list board, not literal beds—overlay names on lined rows is the natural fit. Existing refresh path already recomputes patients; attaching a new file each open satisfies FR-011 without caching.

**Alternatives considered**:
- Rename asset to `admitted.png` → optional follow-up; avoid churn in v1 (document typo).
- Pre-bake empty vs full variants → rejected (need dynamic names).
- Drop text patient field when image present → rejected (overflow + ETA math copy still needed).

## R5 — Schema / RPC changes

**Decision**: **None.** Purchase, swap, admit/discharge math stay server-side as today. UI may disable refill before RPC; economy may still clip energy if somehow invoked—UI guard is primary UX.

**Rationale**: Spec FR-015 and Assumptions.

## R6 — Testing strategy

**Decision**: Unit-test near-full matrix (0/max, max-5, 95% boundary, fail-open). Unit-test hospital slot capping helper (e.g. `patient_overlay_rows(patients, max_slots=6)`). Keep `test_squad_swap_confirm` green; add attachment-filename assertion only if cheap. Manual Discord quickstart for visual QA.

**Rationale**: PIL golden images are brittle; pure logic + smoke “returns File when asset exists” is enough.

## Resolved clarifications

| Topic | Resolution |
|-------|------------|
| Near-full formula | OR of ≥95% and within 5 of max; full vs near labels |
| Swap visual | Side-by-side cards |
| Hospital art | `assets/admited.png` row overlays, max 6 |
| Migrations | None |
| Agent context script | Not present in `.specify/scripts` — skipped |
