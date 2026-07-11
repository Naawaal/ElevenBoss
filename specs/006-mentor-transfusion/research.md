# Research: Mentor Transfusion — Pre-Integration Assessment

**Feature**: `006-mentor-transfusion` | **Date**: 2026-07-11  
**Purpose**: Freeze context before `/speckit.plan` so implementation prioritizes zero downtime and does not regress progression/economy pipes.

---

## 1. What We Have (Current State)

### 1.1 Product surfaces (manager-facing)

| Surface | Entry | Role today |
|---------|--------|------------|
| Development hub | `/development` | Drills, fusion, evolutions, Allocate Skills, claim level rewards |
| Allocate Skills | Hub `⭐ Allocate Skills` → `show_skills_menu` | Roster select + 6 stat buttons → RPC `allocate_skill_point` |
| Player profile | `/player-profile` (and related) | Shows available SP; Allocate button if SP > 0 → same skills menu |
| Store | `/store` | Daily login + energy refill only — **no SP/XP** |
| Marketplace | `/marketplace` | Card trade value — **no mentor awareness** |
| Battle / league | `/battle`, league rewards | Match XP via `process_match_result` → `apply_card_xp` |

**Maxed-card pain today:** Cards at OVR ≥ POT can still earn SP from level-ups, but `allocate_skill_point` rejects spends. UI still shows allocate when `skill_points > 0`; managers hit a dead end. `can_allocate_skill_point` is imported in `development_cog.py` but **not used** to pre-disable illegal stats.

### 1.2 Progression architecture (do not fork)

```
Match / Drill / Fusion
        ↓
   apply_card_xp(card, xp, source)     ← SINGLE XP PIPE (AGENTS §7)
        ↓
 level-ups → skill_points += 3/level
        ↓
 allocate_skill_point(stat)            ← SINGLE SP SPEND PIPE
```

| Concern | Authority |
|---------|-----------|
| XP curve / SP per level / caps (Python mirror) | `packages/player_engine/player_engine/progression.py` |
| Allocate gate (pure) | `packages/player_engine/player_engine/progression_gates.py` → `can_allocate_skill_point` |
| Match XP wiring | `apps/discord_bot/core/match_xp.py` → `process_match_result` |
| Apply XP RPC | `apply_card_xp(p_card_id, p_xp_amount, p_source)` — SECURITY DEFINER (048/049); body hardened in 038 |
| Allocate RPC | `allocate_skill_point` — body in `027_progression_hardening.sql` |
| Fusion pattern (closest cousin) | `train_with_fodder` — daily log + coin sink + `apply_card_xp(..., 'fusion')` |

**Key constants (mirror SQL ↔ Python):**

| Constant | Value |
|----------|-------|
| `POINTS_PER_LEVEL` | 3 |
| `L_MAX` | 100 |
| `ALLOCATION_DAILY_CAP` | 15 (until `2026-08-06` UTC) |
| `MATCH_XP_DAILY_CAP` | 100 / card / day (`match_simulation` only) |
| `FUSION_DAILY_LIMIT` | 3 / club / day |

**At max level (`L_MAX`):** `apply_card_xp` wastes XP (`xp_wasted`); no SP grant. Mentor target grants must respect this.

### 1.3 Data model (relevant columns)

| Table | Columns / notes |
|-------|-----------------|
| `player_cards` | `xp`, `level`, `skill_points`, `skill_points_earned`, `skill_points_spent`, `overall`/`potential`, `daily_alloc_count`, `alloc_reset_date`, match/drill daily fields |
| `player_xp_log` | Append-only XP grants by `source` |
| `fusion_daily_log` | Precedent for club/day caps |
| `pending_level_rewards` | Retro SP claims (unrelated to mentor spend) |

**Latest migration in repo:** `051_card_role_persistence.sql` → next mentor work is **`052+`**.

### 1.4 Background jobs (touch cards, not mentor)

| Job | Progression impact |
|-----|--------------------|
| Season aging / youth intake / regen pool | Lifecycle only |
| Daily recovery | Fatigue/injury only |
| League auto-sim → rewards | Match XP path (leave alone) |
| Pending level-reward notifier | Retro SP DMs |

### 1.5 Explicitly unchanged systems

Match engine (`v2_simulator`), match XP rates, coin/`apply_club_economy` faucets, energy, marketplace valuation formulas, league LP/divisions, aging/retirement, fusion coin sink.

---

## 2. What To Change (Touch List)

### 2.1 Project rule / SDD files

| File | Change |
|------|--------|
| `specs/006-mentor-transfusion/spec.md` | **Done** — feature requirements |
| `specs/006-mentor-transfusion/plan.md` | Next: `/speckit.plan` — migration 052, RPC, UI wiring |
| `.specify/feature.json` | Point at `specs/006-mentor-transfusion` |
| `AGENTS.md` / `.agents/AGENTS.md` | After ship: document mentor as SP→XP pipe via new RPC + `apply_card_xp` (do not invent a second XP path) |
| `change_log.md` | Player-facing note when shipping |
| `.specify/specs/v1.0.0/spec.md` + `plan.md` | Reconcile when behavior is approved (AGENTS §5) |

### 2.2 Configuration / domain constants (new)

| Location | Proposed |
|----------|----------|
| `packages/player_engine/.../mentor_math.py` (new) | `SP_PER_MENTOR_UNIT = 5`, `XP_PER_MENTOR_UNIT = 500`, `MENTOR_TRANSFERS_DAILY_LIMIT = 3`, conversion helpers, eligibility helpers |
| `packages/player_engine/player_engine/__init__.py` | Export mentor math |
| `packages/player_engine/player_engine/progression.py` | Prefer **not** to overload; keep mentor constants in `mentor_math.py` |
| SQL RPC constants | Mirror the same three numbers inside `transfer_mentor_xp` |
| `game_config` | **Not required for v1** (allocation/fusion mentor rates are code constants today; same pattern) |

### 2.3 Domain / schema / app files (expected plan surface)

| Layer | Touch |
|-------|-------|
| Migration `052_mentor_transfusion.sql` | Table `mentor_transfer_log`; RPC `transfer_mentor_xp`; RLS; schema guard |
| `supabase/scripts/verify_required_schema.sql` | Guard table + RPC (+ policies) |
| `apps/discord_bot/cogs/development_cog.py` | Maxed-card branch → Mentor Transfer views (target, amount, confirm) |
| `apps/discord_bot/cogs/player_cog.py` | Mentor Ready copy on profile when eligible |
| `apps/discord_bot/core/api_errors.py` | Map new RPC error codes to manager copy |
| `tests/` | `test_mentor_math.py` (+ RPC contract tests if pattern exists) |
| Embeds/views | Prefer extend existing development/player modules; avoid new slash commands |

**Reuse pattern:** `train_with_fodder` (atomic RPC, daily log table, UI under `/development`, XP only via `apply_card_xp` with a distinct `p_source`, e.g. `'mentor_transfer'`).

---

## 3. What To Protect (Risk Assessment)

### 3.1 Database migration safety

| Risk | Mitigation |
|------|------------|
| Half-applied SP/XP | Single RPC transaction: lock rows → validate → debit SP → `apply_card_xp` → insert log → commit |
| Wrong column invented | Columns only in new migration; extend verify guard |
| Break `apply_card_xp` | **Do not** replace `apply_card_xp`; call it with new source string |
| RLS empty-table trap | Enable RLS + policies for `mentor_transfer_log` in same migration (AGENTS §8) |
| Remote already at 051 | Forward-only `052+`; never edit applied migrations |
| Downtime | Additive table + new function only; no rewrite of `player_cards` shape; bot deploy after migration verify |

### 3.2 Backward compatibility

| Concern | Stance |
|---------|--------|
| Existing allocate flow | Unchanged for non-maxed cards |
| Existing surplus SP | Immediately usable — no backfill required |
| Old bot binary vs new RPC | Safe: old bot never calls new RPC; new bot must not call until migration verified |
| Old bot vs new UI | Ship migration first, then bot; UI gates on eligibility |
| `skill_points` invariant | Debit must keep `skill_points` / `skill_points_spent` (or earned) accounting consistent with allocate semantics — plan must pick one accounting model and match SQL |
| Match XP daily cap | Mentor source string must **not** be `match_simulation` |

### 3.3 Feature flagging (new vs old)

**v1 recommendation (ponytail):** No external feature-flag service.

| Layer | “Off” behavior | “On” behavior |
|-------|----------------|---------------|
| DB | RPC exists but unused | Bot calls RPC |
| UI | No Mentor button (deploy without UI or gate behind env if needed) | Show for eligible maxed cards only |
| Data | Empty `mentor_transfer_log` | Append-only |

Optional soft flag: `MENTOR_TRANSFUSION_ENABLED` env on the bot only (hide UI + skip RPC). Schema can remain deployed. Rollback = disable flag / revert bot; **do not** DELETE historical log rows.

---

## 4. What Might Fail (Edge-Case Checklist)

### 4.1 High-traffic manager flows

- [ ] Double-tap Confirm on Mentor Transfer (idempotency / row locks)
- [ ] Two devices transferring from same source simultaneously
- [ ] Transfer while Allocate Skills stale embed still open
- [ ] Transfer during matchday lock / `assert_not_in_match` on source or target
- [ ] Source sold on marketplace between preview and confirm
- [ ] Target sold / claimed by another flow between preview and confirm
- [ ] Club at exactly 3 transfers; race on 4th
- [ ] Source drops below 5 SP from a concurrent allocate attempt (should be impossible if maxed, but guard anyway)
- [ ] Target reaches POT/level cap inside `apply_card_xp` mid-grant (`xp_wasted` handling + SP already deducted — **critical design**: validate convertible XP against remaining headroom **or** accept waste with explicit preview)

### 4.2 Asynchronous jobs & lifecycle

- [ ] Season aging / retirement of source after transfer (history retained; no clawback)
- [ ] Youth intake creating new targets mid-day (eligible immediately)
- [ ] Pending level-reward claim granting more SP to a maxed source mid-session
- [ ] Daily UTC rollover at cap boundary (transfer #3 at 23:59, #1 at 00:00)
- [ ] Allocation pacing window end date (`2026-08-06`) — mentor must not depend on alloc cap remaining forever

### 4.3 Third-party / platform dependencies

- [ ] Discord 3s interaction window — defer immediately on all mentor callbacks
- [ ] Ephemeral vs public hub messages — follow Development hub patterns
- [ ] Persistent views after bot restart — register any persistent mentor views in `main.py` if needed (prefer short-lived views like fusion)
- [ ] Supabase RPC timeouts under load — keep work inside one RPC; no app-level multi-update loops
- [ ] DMs disabled — mentor does not need DMs; stay on hub/profile

### 4.4 Economy / integrity (regression)

- [ ] No `players.coins` mutation
- [ ] No energy mutation
- [ ] No bypass of `apply_card_xp`
- [ ] No direct `UPDATE player_cards SET xp/level`
- [ ] Fusion daily log and mentor daily log remain independent
- [ ] Match XP amounts unchanged
- [ ] Marketplace price formula unchanged (perception-only retention)

### 4.5 Product edge cases (from gameplay analysis)

| Scenario | Expected |
|----------|----------|
| Source not maxed | Reject |
| Target maxed | Reject |
| Cross-club cards | Reject |
| SP &lt; 5 | UI grey + RPC reject |
| 4th transfer same UTC day | Reject |
| Target in drill / match lock | Reject |
| Source injured | Allow |
| Sell source after transfer | Keep target XP |
| Many maxed sources | Shared club daily cap 3 |
| Youth levels fast via mentor | OK; stat allocation still paced |

---

## 5. Decisions Locked for Planning

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Extend `/development` + profile only; no new slash command | AGENTS scope + product brief |
| D2 | New atomic RPC `transfer_mentor_xp` + append-only `mentor_transfer_log` | Fusion cousin; FR-013 audit; Database Rule |
| D3 | Pure math in `packages/player_engine/mentor_math.py` | Monorepo Rule |
| D4 | 5 SP → 1 MP → 500 XP; 3 transfers/club/UTC day | Product analysis |
| D5 | Cross-position allowed | Product analysis Option B |
| D6 | No coin/energy cost in v1 | Product “store unchanged” |
| D7 | Soft bot env flag optional; no flag service required | Zero-downtime rollback |
| D8 | Migration `052+` after verify; then bot UI | AGENTS migration workflow |
| D9 | SP debit: `skill_points -= 5N` and `skill_points_spent += 5N` | Keeps earned−spent invariant; see R1 |
| D10 | Reject any transfer that would waste XP; Max = min(SP units, XP headroom units) | See R2 |
| D11 | Source maxed = `overall >= potential`; target eligible = same club, `overall < potential`, `level < L_MAX` | See R3 |
| D12 | Profile = Mentor Ready copy only (no new CTA button in v1) | See R4 |
| D13 | Busy lock = club `assert_not_in_match` only (drills are sync; no persistent in-drill flag) | See R5 |

---

## Phase 0 decisions (plan resolution)

### R1 — SP accounting on debit

**Decision**: On successful transfer of `N` mentor units, update source as:
`skill_points = skill_points - (5*N)`, `skill_points_spent = skill_points_spent + (5*N)`.
Do **not** add a `skill_points_mentored` column in v1.

**Rationale**: Existing invariant is `skill_points ≈ skill_points_earned − skill_points_spent`. Debiting available SP without bumping spent breaks that invariant and any future audits/reconcilers. Treating mentor conversion as “spent/consumed” matches allocate’s consumption semantics even though the destination is XP, not a stat.

**Alternatives considered**:
- Decrement `skill_points` only — breaks invariant.
- New `skill_points_mentored` column — YAGNI; complicates schema for one sink.
- Soft-delete SP into a holding bucket — overbuilt.

### R2 — XP waste policy

**Decision**:
1. RPC **rejects** the entire transfer if `apply_card_xp` would report `xp_wasted > 0` for `500*N` (pre-check with remaining XP to `L_MAX`, or call simulate then abort before debit).
2. UI **Max** button = `min(floor(source_sp/5), floor(xp_headroom_to_L_MAX/500), remaining convertible)` so managers cannot pick a wasting amount from the happy path.
3. Never partially grant then waste after debiting SP.

**Rationale**: Spec SC-006 requires exact `5N` SP and `500N` XP into the pipe; wasting after debit would strand SP. Reject-or-cap preserves atomic all-or-nothing.

**Alternatives considered**:
- Allow waste (fusion-like) — managers lose SP silently; violates “no silent corruption.”
- Partial grant of absorbable XP only — breaks fixed 5:1:500 chunks mid-transfer.

### R3 — Eligibility predicates

**Decision**:
- **Source eligible**: `owner_id = club`, `overall >= potential`, `skill_points >= 5`.
- **Target eligible**: `owner_id = club`, `id != source`, `overall < potential`, `level < 100` (can absorb ≥ 500 XP after headroom check).
- Potential ceiling uses stored `overall` / `potential` columns (same values `allocate_skill_point` uses), not a recompute of True OVR in the RPC.

**Rationale**: Matches product “potential ceiling” language and today’s allocate failure mode. Level cap is required because `apply_card_xp` wastes at `L_MAX` even if OVR &lt; POT.

**Alternatives considered**:
- Source must also be `level == 100` — too strict; many POT-maxed cards still level for SP.
- Recompute True OVR in RPC — drift risk vs stored overall; allocate already trusts stored overall.

### R4 — Profile CTA

**Decision**: v1 profile shows Mentor Ready conversion text only. Existing Allocate Skills button (when SP &gt; 0) remains the entry into Development; no separate Mentor button on profile.

**Rationale**: FR-010 is informational; YAGNI on a second CTA. Development remains the transfer surface (FR-008).

**Alternatives considered**:
- Deep-link Mentor button on profile — polish; defer to a later pass if discovery metrics warrant it.

### R5 — Busy / drill locks

**Decision**: Gate transfers with existing club-level `assert_not_in_match` (bot) and matching ownership/existence checks in RPC. Do **not** invent a persistent “in drill” flag — drills are synchronous RPCs with no durable busy row today.

**Rationale**: Spec asked for drill parity with Development norms; current Development only has match lock. Matching reality avoids fake schema.

**Alternatives considered**:
- Block if card appears in a hypothetical drill session table — no such table exists.

### R6 — Daily cap storage shape

**Decision**: Append-only `mentor_transfer_log` with one row per successful transfer. Enforce cap via `COUNT(*)` for `(club_id, transfer_date = CURRENT_DATE) < 3` under row locks on source/target (and optional advisory lock on club day). Do **not** reuse a fusion-style counter-only table as the sole store (counter may be maintained as denormalized optimization later; v1 = append-only).

**Rationale**: FR-013 requires auditable history (who mentored whom, SP/XP amounts).

---

## 6. Assessment Verdict

Mentor Transfusion is a **narrow, additive progression sink** with clear reuse of `apply_card_xp` and an append-only daily log. Highest integration risks are double-submit under Discord UI and near-ceiling XP headroom — both addressed by R2 + row locks. Match, economy, and marketplace code paths stay untouched.
