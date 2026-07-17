# Research: League Dynamics Overhaul (020)

**Date**: 2026-07-15  
**Purpose**: Bridge research proposal ↔ codebase; freeze implementation decisions for Speckit plan.

---

## 1. Audit — Current guild league (summary)

| Piece | State |
|-------|--------|
| Surfaces | `/league hub` (`league_cog.py`); admin open/start/end (`admin_cog.py`); play via `battle_cog` |
| Windows | Rolling: `window_duration = duration_days / total_matchdays` from **admin start time** — not UTC midnight |
| Default length | **28 days**; sizes 8/10/12/16; double RR → `(N−1)×2` matchdays |
| Auto-sim | Python `auto_sim_expired_fixtures`; APScheduler **every 10 min** + hub open |
| Matchday advance | Python `update_current_matchday` → prizes RPC on last MD |
| Prizes | RPC `distribute_season_prizes` — flat human table, 60/25/10 + participation |
| Threads | Journal + MatchDay (`034`); reminders 6h before `window_end` (`035`) |
| Divisions | **None** on seasonal participants. Weekly ladder uses `players.division` + 20% Mon reset |
| MoMD | **Does not exist**. Card MOTM ≠ manager award. Fixtures have **no** `resolved_by` |

There is no `league_results` table; scores live on `league_fixtures`.

Full audit lived in the specify pre-work; this file freezes choices only.

---

## 2. Competitive research — validated

| Pattern | Peer | Discord-fit decision |
|---------|------|----------------------|
| Daily tick | Top Eleven / FM | **UTC 00:00 hard close** + 00:05 batch — shared ritual without live attendance |
| Short seasons | Engagement games | **14 days** with 8-club double RR |
| Pyramid | FM | Seasonal tiers only; **do not** merge weekly Division Rank |
| Mid-cycle award | EA FC / FM | MoMD coin + **one Journal line**; manual play only |

Rejected for v1: live attendance, 10-club uneven RR, Meriging ladders, MatchDay spam for MoMD.

---

## 3. User & PM lens

| Concern | Verdict |
|---------|---------|
| 24h anxiety | Mild; mitigated by Discord `<t:…:R>` countdown, 6h DM, habit formation; weekend AFK → auto-sim (acceptable) |
| Auto-split | 9th human → Div 2 keeps Div 1 exclusive; bot fill preserves math |
| MoMD clutter | One Journal announcement/day/guild season; skip if no manual win |

---

## 4. Decisions

### D1–D2 Feature flag + pacing_mode

**Decision**: Global `league_dynamics_enabled` (default false). At `admin_start_season`, if flag on → insert season with `pacing_mode='dynamics'`; else `'legacy'`. Backfill existing seasons to `'legacy'`.

**Rationale**: Grandfathers live competitions (SC-006) without per-fixture rewrites.

**Alternatives**: Mid-season window rewrite — rejected (breaks reminders/expectations). Per-guild flag only — deferred; global is enough for pilot.

### D3–D4 / D15 Season length + UTC windows

**Decision**: Dynamics forces 14 days and 8 clubs/tier.  
`window_end(N) = utc_midnight_floor(start_time) + N days`.

**Rationale**: Exact alignment 14 MD ↔ 14 calendar midnights. First MD may be &lt;24h if admin starts mid-day — acceptable; quickstart recommends starting near 00:00 UTC for pilot.

**Alternatives**: Rolling 24h from start — rejected (no shared tick). Always wait until next midnight to open MD1 — nicer but delays kickoff; can soft-document as ops tip without code.

### D5 Scheduler split

**Decision**: Cron 00:05 UTC for Dynamics; interval 10 min for legacy only.

**Rationale**: Shared “league night”; avoids double-simming Dynamics every 10 min while preserving soft legacy close.

**Alternatives**: Single job always interval — fails “shared moment” narrative. Kill interval entirely — leaves legacy seasons lagging until hub open.

### D6–D8 Multi-tier seating + promo

**Decision**: One season row; `division_tier` on participants; fixtures intra-tier; persist swaps on `league_members.seasonal_division_tier`.

**Rationale**: One Journal/MatchDay pair; synced matchdays; least new slash/admin UX.

**Alternatives**: N season rows per division — more thread spam and prize glue. Max-10 single RR — rejected in specify Q1=A.

**Promo helper**: New `compute_fixed_promo_relegation(standings, n=2)` — **do not** reuse weekly 20% `compute_promotions_relegations` (wrong cut).

### D9–D11 MoMD

**Decision**: Persist `resolved_by`; eligibility manual human wins; one award/`(season, matchday)`; 2000 coins config.

**Rationale**: Spec Q3=A; need stored signal because `active_player_id` is ephemeral.

**Alternatives**: Infer manual from match_runs presence — brittle. MoMD per division — more Journal noise; SC-005 says one.

### D12–D14 Prizes / decoupling / migration

**Decision**: Per-tier prize distribution inside existing RPC; weekly ladder untouched; migration **064**.

---

## 5. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| MoMD inflation | Tunable `league_momd_coins`; economy watch in rollout |
| Short MD1 window | Ops tip: start near midnight UTC; optional later soft delay |
| Label confusion Div vs Weekly Rank | Hub copy contract |
| Tick load (many guilds × fixtures) | Sequential sim with small sleep (existing); monitor SC-001 |
| Fee charge then re-seat | Charge fees after seating / recompute bot fill if humans skipped (existing fee path) |

---

## 6. Resolved clarifications (from specify)

| Q | Choice |
|---|--------|
| Q1 Size | **A** — exactly 8/tier, bot fill |
| Q2 Split | **A** — humans &gt; 8 → next tier |
| Q3 MoMD | **A** — manual human wins only |
