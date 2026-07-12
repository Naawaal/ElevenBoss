# Research: Recovery Energy, Hub Cleanup & Energy Cap

**Feature**: `010-recovery-energy-cleanup` | **Date**: 2026-07-12  
**Purpose**: Resolve how to ship four small product tweaks without breaking dual-written energy columns or orphaning Hospital/finance flows.

---

## R1 — Recovery Session energy 10 → 5

**Decision**: Update `game_config.fatigue_recovery_energy` to `5` via migration `055` (`ON CONFLICT DO UPDATE`). Change SQL fallback in `process_recovery_session` from `10` to `5`. Bot already reads config (`get_game_config_int(..., basic_energy_cfg)`); ensure Development default when config missing is **5**, not Basic-drill energy.

**Rationale**: Spec wants Recovery cheaper than Basic drills (~10). Dedicated key already exists from `054`.

**Alternatives considered**: Hardcode 5 only in Python — rejected (RPC is source of truth for debit).

---

## R2 — Energy max 100 → 120 (schema blocker)

**Decision**: Migration `055` must:

1. Drop/replace `players.energy` and `players.training_energy` CHECKs that enforce `<= 100` (from `001` / `015`) with `<= 120` (or a looser ceiling ≥ 120). Dual-write in `sync_action_energy` / `apply_club_economy` writes all three columns together — without this, regen/refill above 100 **fails**.
2. `UPDATE game_config SET value_json = '120' WHERE key = 'energy_max'` (upsert if missing).
3. `UPDATE players SET max_energy = 120 WHERE max_energy < 120` (and optionally `action_energy`/`energy`/`training_energy` defaults).
4. `ALTER COLUMN` defaults for `action_energy` / `energy` / `max_energy` / `training_energy` to 120 where applicable.
5. Replace `register_new_player` INSERT to seed `max_energy = 120` (and starting energy pool consistent with full cap).
6. Update Python defaults: `packages/energy/energy/models.py`, `economy_rpc.py` function defaults (`maximum: int = 120`), bot `.get("max_energy", 120)` fallbacks.
7. Fix hardcoded `` `{training_energy}/100` `` in `development_cog.py` to use dynamic max from sync.
8. Adjust `tests/test_match_loop_hardening.py` if it assumes max=100 for time-to-full (either pass 120 or keep explicit 100 as a *parameterized* max for formula purity — prefer keep formula tests with explicit max args; add one assert for default 120 if defaults change).

**Do not** rewrite every historical migration body; forward-fix only in `055`.

**Alternatives considered**: Cap only `action_energy` at 120 while clamping legacy columns at 100 — rejected (dual-write would corrupt/clamp incorrectly).

---

## R3 — Remove Hospital from Store facilities only

**Decision**: Edit `store_facilities.py` facilities hub embed + `FacilitiesHubView` — remove Hospital field, Upgrade Hospital, Hospital Panel buttons, and Hospital mentions in description/footer. **Keep** `HospitalPanelView`, `show_hospital_panel`, upgrade-on-panel (Profile uses `origin="profile"`).

**Copy updates** (Store → Profile pointers):
- `profile_embeds.py` `L0_EMPTY`
- `api_errors.py` injured Recovery message
- `development_cog.py` injured drill/recovery messages
- `injury_rpc.py` overflow DM
- `change_log.md`

**Alternatives considered**: Delete HospitalPanelView — rejected (Profile Manage Hospital depends on it).

---

## R4 — Delete `/club-finances` slash command

**Decision**: Remove only the `@app_commands.command(name="club-finances")` method from `economy_cog.py`. Keep `build_club_finances_embed`, `fetch_club_finances_embed`, `show_club_finances_panel`, `ClubFinancesPanelView` for Profile Finances.

**Deploy note**: After bot restart, Discord command sync drops the removed command (project’s existing sync path).

**Alternatives considered**: Soft-deprecate forever — rejected (spec FR-008).

---

## R5 — Scope of “no references remain”

**Decision**: Player-facing bot strings + `change_log.md` + README command tables if present. Do **not** rewrite historical `.specify` feature specs for 002/003 except reconcile `v1.0.0` on implement. Feature `010` docs are the forward truth.

---

## Resolved clarifications

| Topic | Resolution |
|-------|------------|
| Hospital system deleted? | No — Profile only |
| `/club-finance` vs `/club-finances` | Remove `/club-finances` |
| Energy CHECK ≤100 | Must raise in `055` |
| Recovery vs Basic drill coupling | Keep independent keys |
