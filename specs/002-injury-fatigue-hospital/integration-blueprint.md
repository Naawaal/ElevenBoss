# Integration Blueprint: Fatigue, Injury, Bench & Hospital

**Feature**: `specs/002-injury-fatigue-hospital`  
**Created**: 2026-07-11  
**Status**: Pre-implementation audit (SDD Phase 1)  
**Companion**: [spec.md](./spec.md) (user-facing requirements)  
**Next**: `/speckit.plan` after clarifications resolved

This document maps the attached GDD onto the **actual** ElevenBoss codebase. GDD file names like `match.py` / `store.py` / `players.fatigue` are corrected to real paths and schema.

---

## 1. Audit of Existing Systems

### 1.1 What already exists

| GDD concept | Production status | Where |
|-------------|-------------------|--------|
| Per-player fatigue / fitness | **Not persisted.** Generator dataclass has `fitness=100` flavor only. Interval engine has in-match fitness dict — **not used by Discord**. | `packages/player_engine/.../generated_player.py`; `packages/match_engine/match_state.py` |
| Injury tiers / hospital | **None** in DB, RPCs, or Discord UI | — |
| Cosmetic in-match INJURY | **Yes** — ~1–2% ticker events, no card mutation, no sub | `packages/match_engine/match_engine/v2_simulator.py` |
| Full injury + fatigue + auto-sub loop | **Yes in legacy interval engine only** | `injury_service.py`, `substitution_service.py`, `match_engine.py`, `match_config.py` |
| Club action energy | **Live** — club pool, lazy regen, refill shop | `players.action_energy`; `sync_action_energy`; `/store` |
| Club facilities | **Live** — Youth Academy + Training Ground only | `043_club_facilities.sql`; `store_facilities.py` |
| Squad “bench” | **Pre-match reserves only** via `swap_squad_players` | `squad_cog.py` — **not** in-match subs |
| Match stream pause / `generator.send()` | **Does not exist** | Live path: `async for ev in stream_match(...)`; tactics mutate `MatchState` |

### 1.2 Energy vs fatigue (conflict resolution)

| Resource | Scope | Purpose | Recovery |
|----------|-------|---------|----------|
| **Action energy** | Club (`players` row) | Gate starting matches / drills / evolutions | Lazy regen (~+1 / 4 min) + coin refills |
| **Fatigue** (new) | Player card (`player_cards`) | Match performance + injury risk | Passive daily / hospital / bench rest |

**Rule (non-negotiable):** Fatigue must not refill, spend, or bypass `action_energy`. A rested squad with 0 club energy still cannot start an energy-gated match. Energy refills must not restore card fatigue.

### 1.3 Facilities extension point (Hospital)

Existing pattern is the correct home for Hospital:

- Schema: `players.youth_academy_level`, `players.training_ground_level`, `players.facility_last_upgrade_at`
- RPC: `upgrade_club_facility(p_owner_id, p_facility_key, p_expected_cost)` — keys today: `'youth_academy' | 'training_ground'`
- UI: `/store` → Club Facilities (`apps/discord_bot/views/store_facilities.py`)
- Pure costs: `packages/economy/economy/facility_effects.py` — ladder **750 / 2000 / 5000 / 12000**

**Do not** invent `/hospital` or `/facilities` unless product explicitly wants a new surface (AGENTS.md scope rule). Extend Club Facilities with a third card: Medical Center / Hospital.

### 1.4 Match engine accommodation

**Live path (must change):** NSS v2 `stream_match` in `v2_simulator.py`, consumed by:

- `StandardMatchHandler` / bot loop — `apps/discord_bot/cogs/battle_cog.py`
- `LeagueMatchHandler` / `run_league_match_simulation`
- Friendly inline loop (sandbox — keep out of fatigue/injury by default)

**Already present:**

- `EventType.INJURY` in `models.py`
- Commentary templates for `INJURY` in `commentary_bank.json`
- League UI emoji `🩹` for INJURY; bot/friendly loops currently omit it from key-event maps

**Missing for GDD:**

- Dead-ball pause + manager choice (no `generator.send`; use `MatchState` flags + `asyncio.Event` / wait in the Discord consumer)
- Fatigue multiplier on `phase_stat_value()` 70/30 blend (`phase_stats.py`)
- Bench list on `MatchState` / team state
- Persistent post-match injury + fatigue writes

**Legacy interval engine:** Keep as reference for formulas (`injury_service`, `substitution_service`, `match_config` thresholds). Prefer **porting math into small pure modules** and wiring NSS — do not switch Discord back to the interval simulator.

### 1.5 Critical GDD → schema name corrections

| GDD says | Actual ElevenBoss |
|----------|-------------------|
| `players.fatigue` | **`player_cards.fatigue`** (`players` = club/manager) |
| `clubs.hospital_level` / `clubs.coins` | **`players.hospital_level`**, **`players.coins`** |
| `upgrade_hospital` direct coin UPDATE | Extend **`upgrade_club_facility`** + **`apply_club_economy`** |
| `match.py` | `apps/discord_bot/cogs/battle_cog.py` |
| `store.py` | `apps/discord_bot/cogs/store_cog.py` + `views/store_facilities.py` |
| `squad.py` | `apps/discord_bot/cogs/squad_cog.py` |
| `player_profile.py` | `apps/discord_bot/cogs/player_cog.py` (`build_player_profile`) |
| `development.py` | `apps/discord_bot/cogs/development_cog.py` |
| Daily aging APScheduler for recovery | Aging is **weekly Mon 00:00**; energy is **lazy**. Add a dedicated recovery job or lazy sync RPC |
| Hospital 100k–4M coins | **Out of scale** vs facility 750–12k and bot win ~200 coins — must recalibrate |

---

## 2. File & Code Modification Map

### 2.1 New files (recommended)

```text
packages/player_engine/player_engine/fatigue.py          # drain, recovery rates, penalty tiers
packages/player_engine/player_engine/injury_math.py       # chance, tier weights, hospital recovery days, beds
packages/economy/economy/facility_effects.py             # MODIFY — hospital costs/labels (not a new file)
apps/discord_bot/views/match_injury_prompt.py            # Select + Play On + 30s timeout (Phase 3)
apps/discord_bot/embeds/hospital_embeds.py               # Hospital panel embed builders
apps/discord_bot/core/injury_rpc.py                       # thin wrappers: process_post_match_injuries, admit/discharge
supabase/migrations/050_player_fatigue_injury.sql        # columns + hospital + patients + RPCs (number may shift)
tests/test_fatigue_injury_math.py                        # pure formula checks
```

Ponytail note: Prefer **one** migration file for schema+RPCs+RLS+verify guards unless size forces a split. Prefer extending `facility_effects.py` over `facility_costs.py`.

### 2.2 Existing files to modify

| File | Exact changes |
|------|----------------|
| `packages/match_engine/match_engine/models.py` | Extend `MatchPlayerCard` with `fatigue`, `card_id`; richer injury payload fields on events if modeled |
| `packages/match_engine/match_engine/phase_stats.py` | Apply fatigue (and Play On 0.50) multiplier to **phase attribute** before 70/30 blend |
| `packages/match_engine/match_engine/v2_simulator.py` | Replace cosmetic INJURY with stateful rolls; optional pending-injury until stoppage; remove injured from zone averages for 10-men; accept bench on team state |
| `packages/match_engine/match_engine/commentary_bank.json` | Tags: `substitution`, `down_to_ten_men`, `emergency_goalkeeper`, `played_through_injury` |
| `apps/discord_bot/core/match_cards.py` | `card_from_db_row` loads `fatigue` / injury fields into `MatchPlayerCard` |
| `apps/discord_bot/cogs/battle_cog.py` | Pass bench snapshot into match state; on `INJURY` (Phase 3) await UI; post-match call fatigue drain + injury RPC; include INJURY in bot/friendly key maps when relevant |
| `apps/discord_bot/core/match_rewards.py` / `league_rewards.py` | After economy + XP, call fatigue/injury post-match helpers (order: economy → XP → fatigue/injury) |
| `apps/discord_bot/cogs/squad_cog.py` + `embeds/squad_embeds.py` | Fatigue/injury indicators; block injured from XI |
| `apps/discord_bot/cogs/player_cog.py` | Profile: fatigue bar, injury badge, expected return |
| `apps/discord_bot/cogs/development_cog.py` | Block drills (and fusion targets if needed) for injured cards |
| `apps/discord_bot/views/store_facilities.py` | Third facility card: Hospital; wire upgrade key `'hospital'` |
| `apps/discord_bot/cogs/store_cog.py` | Only if hub copy/buttons need Hospital mention |
| `apps/discord_bot/cogs/economy_cog.py` | Show hospital level on finances if YA/TG shown |
| `packages/economy/economy/facility_effects.py` | `hospital` label, costs array, bed/recovery helpers |
| `apps/discord_bot/main.py` + `scheduler_jobs.py` | Register `process_daily_recovery` job (suggest daily UTC, not only Monday) |
| `supabase/scripts/verify_required_schema.sql` | Columns, table, RPCs, RLS policies |
| `change_log.md` | Player-facing note when shipping |
| `.specify/specs/v1.0.0/spec.md` + `plan.md` | Reconcile when feature is approved into main SDD (AGENTS §5) |

### 2.3 Do **not** treat as live targets

| Path | Why |
|------|-----|
| `packages/match_engine/match_engine.py` (interval) | Not Discord live path |
| `packages/training_engine/` | Unused by Discord |
| New `/hospital` slash command | Extend `/store` facilities instead |
| Direct `UPDATE players SET coins` | Violates economy pipe |

### 2.4 In-match pause pattern (Discord-safe)

GDD `generator.send()` is incompatible with current `async for` consumption.

**Approved adaptation:**

1. Engine sets `state.pending_injury = InjuryPending(...)` and yields `INJURY` at next stoppage-like moment (foul / set piece / goal / half boundaries — NSS has no true DEAD_BALL; define stoppage = FOUL, GOAL, SAVE→SET_PIECE, HALF_TIME).
2. Discord handler **stops advancing the async generator**, posts Select Menu + Play On, `await asyncio.wait_for(decision_event.wait(), timeout=30)`.
3. Handler mutates shared `MatchState` (swap squad entry, set `compromised_flag`, or mark removed) — same pattern as `TouchlineView` tactics.
4. Handler resumes `async for`.

Auto-sim league path: no UI; auto-pick best OVR bench or apply 10-men rules inside the consumer/`collect_match_events` wrapper.

---

## 3. Database Schema Migration Strategy

### 3.1 Entity placement (corrected)

```text
players (club)          → hospital_level, (existing coins, action_energy, YA, TG)
player_cards (card)     → fatigue, injury_tier, injury_started_at, injury_recovery_days, in_hospital
hospital_patients       → bed occupancy rows (card_id UNIQUE while active)
```

### 3.2 Proposed migration sketch (`050_…` — renumber if 050 taken)

```sql
-- A) Card fitness / injury
ALTER TABLE public.player_cards
  ADD COLUMN IF NOT EXISTS fatigue INTEGER NOT NULL DEFAULT 100
    CHECK (fatigue BETWEEN 0 AND 100),
  ADD COLUMN IF NOT EXISTS injury_tier INTEGER
    CHECK (injury_tier IS NULL OR injury_tier BETWEEN 1 AND 4),
  ADD COLUMN IF NOT EXISTS injury_started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS injury_recovery_days INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS in_hospital BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill is implicit via DEFAULT 100 for fatigue on ADD COLUMN.

-- B) Club hospital facility (0 = basic first-aid, 5 = max)
ALTER TABLE public.players
  ADD COLUMN IF NOT EXISTS hospital_level INTEGER NOT NULL DEFAULT 0
    CHECK (hospital_level BETWEEN 0 AND 5);

-- C) Admissions
CREATE TABLE IF NOT EXISTS public.hospital_patients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
  player_card_id UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
  injury_tier INTEGER NOT NULL CHECK (injury_tier BETWEEN 1 AND 4),
  admission_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expected_recovery_date TIMESTAMPTZ NOT NULL,
  discharge_date TIMESTAMPTZ,
  CONSTRAINT hospital_patients_one_active UNIQUE (player_card_id)
);

CREATE INDEX IF NOT EXISTS idx_hospital_patients_owner_active
  ON public.hospital_patients(owner_id)
  WHERE discharge_date IS NULL;

ALTER TABLE public.hospital_patients ENABLE ROW LEVEL SECURITY;
-- Policies: SELECT/INSERT/UPDATE for anon, authenticated, service_role
-- (mirror 030_league_members_rls.sql pattern)

-- D) game_config seeds (recalibrated — see §4)
INSERT INTO public.game_config (key, value_json) VALUES
  ('hospital_upgrade_costs', '[1500, 4000, 10000, 25000, 60000]'),
  ('fatigue_passive_per_day', '20'),
  ('fatigue_hospital_per_day', '45'),
  ('fatigue_bench_per_match', '15'),
  ('fatigue_base_drain', '22')
ON CONFLICT (key) DO NOTHING;
```

### 3.3 RPCs (names + responsibilities)

| RPC | Role |
|-----|------|
| `apply_match_fatigue(p_owner_id, p_starter_ids[], p_bench_ids[], p_drain_by_card jsonb)` | Batch fatigue updates; no per-row app loops |
| `process_post_match_injuries(p_owner_id, p_injuries jsonb)` | Auto-admit / overflow JSON; sets card injury fields |
| `process_daily_recovery()` | Fatigue bump; discharge due patients; untreated day decrement |
| `admit_to_hospital` / `discharge_from_hospital` | Manual overflow resolution |
| `upgrade_club_facility` **extended** | Accept `'hospital'`; read `hospital_upgrade_costs` or unified costs |

**Security:** `SECURITY DEFINER` where bot uses anon key; follow `048`/`049` pattern. All coin moves via `apply_club_economy(..., source => 'facility_upgrade')`.

### 3.4 Data consistency notes

- Existing cards: `fatigue DEFAULT 100` — no backfill script required.
- `injury_tier NULL` = healthy.
- Unique active admission: prefer partial unique index `UNIQUE (player_card_id) WHERE discharge_date IS NULL` if soft-history rows are kept (adjust GDD `UNIQUE(player_id)`).
- Fusion/sell: block or auto-discharge in existing RPCs (`train_with_fodder`, agent sale) — grep and extend.
- Verify guard: add `column:public.player_cards.fatigue`, `column:public.players.hospital_level`, `table:public.hospital_patients`, `function:public.process_post_match_injuries`, etc.

### 3.5 GDD SQL anti-patterns to avoid

```sql
-- ❌ GDD sample
UPDATE clubs SET coins = coins - v_cost, hospital_level = v_new_level;

-- ✅ ElevenBoss
PERFORM public.apply_club_economy(p_owner_id, -v_cost, 0, 'facility_upgrade', ...);
UPDATE public.players SET hospital_level = v_new_level WHERE discord_id = p_owner_id;
```

---

## 4. Economic & Balance Integration

### 4.1 Current economy anchors

| Sink / faucet | Approx coins |
|---------------|--------------|
| Bot match win | ~200 (division-scaled) |
| League win | 250–400 |
| Daily login | 100 + streak |
| Energy refill | 200 / 400 / 600 (3/day) |
| Fusion | 200 |
| Facility L1→L5 steps | 750 → 2000 → 5000 → 12000 |
| Weekly facility cap | 1 upgrade / club / 7 days (shared) |

### 4.2 GDD hospital costs vs reality

| Level | GDD coins | Days at ~500 coins/day | Verdict |
|-------|-----------|------------------------|---------|
| 1 | 100,000 | ~200 days | Breaks YA/TG relevance |
| 5 | 4,000,000 | multi-year | Unusable sink |

**Recommendation (pending clarification Q1):** Recalibrate Hospital to a **premium third facility**:

| Upgrade to | Proposed coins | Beds | Recovery mult |
|------------|----------------|------|---------------|
| L1 | 1,500 | 2 | 0.83× |
| L2 | 4,000 | 3 | 0.71× |
| L3 | 10,000 | 4 | 0.625× |
| L4 | 25,000 | 5 | 0.55× |
| L5 | 60,000 | 6 | 0.50× |

- Share **weekly facility cooldown** with YA/TG (one upgrade per week across all three) — strongest anti-inflation lever already in prod.
- Optional: slightly higher match gates than TG (e.g. L3 needs 15 matches).
- **Defer multi-day build timers** in Phase 1–2 (Ponytail); instant level bump like YA/TG unless product insists.

### 4.3 Double-dipping rules

| Action | Energy | Fatigue | Coins |
|--------|--------|---------|-------|
| Start bot/league match | Spend match energy | Drain starters post-match | Match payout |
| Buy energy refill | +action_energy | No fatigue change | Refill cost |
| Passive day tick | None | +20 fatigue (cap 100) | None |
| In hospital | None | +45 fatigue/day + faster injury clock | None |
| Hospital upgrade | None | None | Facility cost via economy RPC |
| Drill | Drill energy | Block if injured; optional small fatigue cost **out of v1** | Drill coins |

---

## 5. UI/UX Integration

### 5.1 Surfaces

| Surface | Command / hub | Change |
|---------|---------------|--------|
| Squad grid | `/squad` | 🟢/🟡/🪫/🔴 fatigue; 🩹 injured; block injured XI |
| Player card | `/player-profile` | Fatigue bar; injury + ETA |
| Club profile | `/profile` | Optional hospital level line |
| Facilities | `/store` → Club Facilities | Hospital card + Upgrade |
| Hospital queue | Same hub sub-view | Patients, waiting list, Discharge |
| Match thread | Battle / league thread | Phase 3: injury Select Menu |
| Development | `/development` | Injured cards disabled in drill selects |
| Overflow | DM + Hospital panel fallback | Discharge vs leave untreated |

### 5.2 In-match injury pop-up (Phase 3)

- Component: `discord.ui.Select` of bench (label: name, pos, OVR, fatigue%) + Button `Play On`.
- Timeout: 30s → auto best OVR eligible.
- Message: edit/followup in match thread (not ephemeral-only — both managers in league may need visibility; bot battles: challenging manager only).
- Register view if persistent across restart mid-match — prefer **non-persistent** match-scoped view tied to the running task (match already holds the asyncio task).

### 5.3 Mockups

Retain GDD §6 mockups with terminology swaps: `$` → coins; Hospital under Club Facilities; fatigue on **cards**.

---

## 6. Conflict Resolution & Design Alignment

| Topic | Alignment |
|-------|-----------|
| Stamina/fitness vs energy | Fatigue = per-card; energy = club gate |
| Training restrictions | Injured → no drills; fatigue penalties do not block drills in v1 |
| Evolution cooldowns | Unchanged; optionally block starting evolution while injured (recommend yes) |
| Match XP / economy | Still `process_match_result` / `apply_match_economy`; add fatigue/injury **after**, do not fork XP pipe |
| Cosmetic INJURY | Must become real or be removed from competitive paths to avoid lying UI |
| Legacy interval fitness | Reference only; NSS is source of live truth |
| Dollars | Coins only |
| Hospital Level | `players.hospital_level` facility |

---

## 7. Implementation Phasing (Ponytail)

| Phase | Ship | Risk | Suggested release |
|-------|------|------|-------------------|
| **1 – Fatigue** | `player_cards.fatigue`; drain RPC; penalties in `phase_stats`; squad/profile indicators; daily/lazy recovery; bench rest | Low | First PR / early v1.x |
| **2 – Injury + Hospital** | Injury columns; post-match rolls; `hospital_patients`; extend facilities UI; admit/overflow; block drills/XI; recovery RPC | Medium | After Phase 1 stable |
| **3 – Live bench subs** | Bench on `MatchState`; stoppage yield; Discord wait UI; 10-men; emergency GK; Play On | Medium–High | Later update — **default defer from first ship** |

### Decision flowchart (product)

```text
Match runs (NSS stream)
  → Phase 1: apply fatigue modifiers continuously from card fatigue
  → Phase 2: post-match injury roll → hospital auto-admit / overflow
  → Phase 3 only: mid-match INJURY yield → Discord pause → sub/Play On → resume
```

### Mathematical formulas (adopt from GDD, implement in packages)

- **Drain:** `Base 22 - PHY*0.15 + tactic(+8/-4/0) + intensity(+5 if 2+ LP tiers)` → int
- **Penalties:** GDD fatigue tier table on phase attribute before 70/30
- **Injury chance:** GDD base 0.4% + fatigue/age/PHY modifiers; tier weights 60/30/9/1
- **Recovery days:** `ceil(BaseTierDays / (1 + 0.2 * hospital_level))`
- **Beds:** `hospital_level + 1`

Tune live rates in `game_config` after playtests — do not hardcode only in SQL.

---

## 8. Actionable Developer Checklist (pre-code)

1. Resolve 3 clarifications in `spec.md` (economy scale, Phase 3 in/out, Tier 4).
2. Run `/speckit.plan` → `plan.md`, `data-model.md`, contracts.
3. Author migration `050+` with RLS + verify guards; apply via `scratch/apply_migration_*.py`.
4. Implement pure math + tests first (`tests/test_fatigue_injury_math.py`).
5. Wire Phase 1 bot/league only; keep friendlies sandbox.
6. Grep all `upgrade_club_facility` / drill / fusion / sell callers before merge.
7. Update `change_log.md` on ship.
8. Persona walkthrough: manager double-tap upgrade; hospital full + DMs off; auto-sim league injury; bot club ignore.

---

## 9. Clarifications — RESOLVED (2026-07-11)

| Q | Decision | Locked default |
|---|----------|----------------|
| Q1 Economy | **A** | Hospital costs **1,500 / 4,000 / 10,000 / 25,000 / 60,000**; shared weekly facility slot |
| Q2 Tier 4 | **A** | Roll 100 → **Major**; no auto-retire in v1 |
| Q3 Live subs | **A** | **Phase 3 deferred**; first ship = fatigue + post-match injury/hospital |

See [plan.md](./plan.md) and [research.md](./research.md) for the implementation plan.
