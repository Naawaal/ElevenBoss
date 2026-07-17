# Research: League Automation & Config (021)

**Date**: 2026-07-15  
**Purpose**: Map autonomous lifecycle onto existing admin/Dynamics surfaces; freeze decisions for plan.

---

## 1. Audit — what already exists

| Piece | State |
|-------|--------|
| Announce channel / role | `guild_config.league_channel_id`, `announcement_role_id` — `/admin` Announcement Settings already |
| Registration / start | Manual `admin_open_registration`, `admin_start_season` |
| Dynamics (020) | `pacing_mode`, 14d, midnight windows, 8/tier, MoMD, promo, `dynamics_daily_tick_job` 00:05 |
| Min humans / reg hours | `league_min_humans` default 2; `league_registration_hours` default **72** (manual) |
| Season status | `registration` \| `active` \| `paused` \| `completed` |
| Journal MoMD | Posted from settlement path already |

Gap: no autonomous open → close → start → conclude → loop; admin still owns Start/Open; no announce digests for daily tick.

---

## 2. Decisions

### D1–D2 Flags & config storage

**Decision**: Global `league_automation_enabled` + optional per-guild override on `guild_config`. Reuse existing channel/role columns.

**Rationale**: Spec FR-001; Ponytail — admin UI already exists; only labels/gates need polish.

**Alternatives**: New `guilds` table — rejected.

### D3–D5 Dynamics coupling & job consolidation

**Decision**: Automation-owned seasons always use Dynamics start/tick path. **Fold** `dynamics_daily_tick_job` into `league_state_machine_job` so one 00:05 runner handles all Dynamics auto-sims (manual Dynamics seasons still get ticks without needing automation announce digests).

**Rationale**: Spec FR-006 — no double-sim races; one clock.

**Alternatives**: Keep both jobs with filters — easy to miss a season and double-process.

### D4 Ownership marker

**Decision**: `config_json.automation = true` on seasons opened/started by the job. Manual admin seasons unmarked.

**Rationale**: Grandfathering (SC-004); job must not steal mid-flight manual seasons.

### D7–D8 Registration hours & under-min Monday reopen

**Decision**: Automation uses **48h** (`league_automation_registration_hours`). Under-min → fail + `next_auto_registration_at` = next Monday 00:05 UTC.

**Rationale**: Spec Q1=C; avoids irregular extensions; aligns with weekly Monday batch culture.

**Alternatives**: Daily retry — rejected (stall). +24h×3 — rejected (complexity).

### D9–D10 Conclude → reg + admin gates

**Decision**: Same-run reopen after conclude when channel OK. Admin Pause/Force End only when automation effective.

**Rationale**: Spec Q2=A + SC-003.

### D11 Extract start core

**Decision**: Pull seating/fixture/thread creation into a shared async function called by admin (automation off) and job.

**Rationale**: Avoid forking 020 seating logic.

### D13 Digest idempotency

**Decision**: Store `config_json.last_digest_matchday` (int) after successful announce digest; skip re-post on retry.

---

## 3. Risks

| Risk | Mitigation |
|------|------------|
| Race admin Start vs job | Hide Start/Open when automation on |
| Missing channel | Skip transitions that need announce? **Frozen:** still open/start if channel missing but **log + admin banner**; prefer **block open** if no channel (safer UX). Spec: missing channel skips posts; transitions may proceed — **tighten:** do **not** auto-open registration without a resolvable channel |
| Folded tick regresses non-automation Dynamics | State machine must process all `pacing_mode=dynamics` active seasons for sim/settlement; digests only if automation effective |
| Monday reopen timezone | Compute next Monday 00:05 UTC in pure helper |

---

## 4. Clarifications locked

| Q | Choice |
|---|--------|
| Under-min | **C** — Monday fresh 48h |
| Admin | **A** — Pause/Force End only |
