# ElevenBoss — Progression & Energy Rebalance Proposal (Draft)

## Goals

- **Engagement**: 20–30 minute daily session without hard walls.
- **Pacing**: Avoid “max in a week” while preventing “glacial” leveling at midgame.
- **Economy health**: Keep energy refills as an optional coin sink (not mandatory to play).
- **Activity diversity**: Drills feel targeted/efficient; battles feel exciting and meaningfully rewarding.
- **Anti-bot**: Replace “momentum-killing cooldowns” with caps where possible.

---

## 1) Current Values Audit (runtime-evidenced)

### Energy system

| Lever | Current |
|---|---|
| **Energy max** | **100** (seeded `game_config.energy_max`) |
| **Regen rate** | **1 per 6 minutes** = 10/hour (seeded `game_config.energy_regen_per_min = 0.1666667`) |
| **Bot battle cost** | **20** energy (`game_config.match_energy_bot`) |
| **Friendly cost** | **15** energy in config, but friendly matches are currently “free” in UI copy and rewards (see risks) |
| **League cost** | **10** energy (`game_config.match_energy_league`) |
| **Drill cost** | **Basic 10**, **Advanced 15** energy (`game_config.drill_basic_energy`, `drill_advanced_energy`) |
| **Energy refill** | +**50** energy, costs **200/400/600**, **max 3/day** (`purchase_energy_refill`) |

Runtime evidence (baseline audit): `debug-465916.log` lines 1 and 7 show regen + costs and derived downtime.

### XP gains

| Source | Current formula / value |
|---|---|
| **Drill XP (base)** | Basic **30**, Advanced **80** (`game_config.drill_basic_xp`, `drill_advanced_xp`) |
| **Drill diminishing returns** | \(xp = \lfloor base / (1 + 0.05\cdot(level-1))\rfloor\) |
| **Match XP per card (bot)** | ~13–23 at typical ratings (cap 35), but costs 20 energy (see “relative value” below) |
| **Match XP per card (league)** | ~16–27 at typical ratings (cap 35) and costs 10 energy |
| **Fusion XP** | \(50 + 8\cdot L_{fodder} + 2\cdot OVR_{fodder}\) (example: L10, OVR60 → **250 XP**) |

Runtime evidence:
- Drill XP at key levels: `debug-465916.log` line 3
- Match XP table + a “good game” cap case: `debug-465916.log` line 4
- Fusion XP example: `debug-465916.log` line 5

### Cooldowns & caps

| Gate | Current |
|---|---|
| **Evolution start cooldown** | **10 hours** (hard-coded constant in `start_player_evolution`) |
| **Max active evolutions** | **3** (hard-coded constant) |
| **Fusion daily limit** | **3/day** (hard-coded) |
| **Drills cap (club)** | **20/day** |
| **Drills cap (per card)** | **5/day** |
| **Match XP cap (per card)** | **100/day** (match XP only) |

Runtime evidence: `debug-465916.log` line 6.

---

## 2) Pain Points Mapped to Numbers (player perspective → lever)

### “I can only do 3 drills before energy runs out, and XP barely moves.”

- **Energy reality**: At 100 max energy, basic drills (10 energy) allow **10 drills**; advanced (15) allow **6 drills**.
  - If players report “3 drills”, it usually implies they are also spending energy on battles/evolutions, or they start a session partially drained.
- **XP reality**: Drill XP falls hard with level due to diminishing returns:
  - Basic drill XP: **L1=30**, **L10=20**, **L25=13** (`debug-465916.log` line 3).
  - Advanced drill XP: **L1=80**, **L10=55**, **L25=36** (`debug-465916.log` line 3).
- **Curve reality**: XP needed per level rises quickly:
  - XP needed: **L1=100**, **L10=277**, **L25=1517** (`debug-465916.log` line 2).
- **Resulting feel**: Midgame (L25) a player doing only advanced drills at 36 XP/drill needs ~**42 drills** for one level, but is capped at **5 drills/card/day** → ~**8.4 days** per level from drills alone.

### “Bot Battle costs a big chunk of energy but gives similar XP to a drill.”

This is the biggest *relative* imbalance:

- Bot match XP per card (90m, rating ~6, win) ≈ **19** XP (`debug-465916.log` line 4).
- Basic drill XP at L10 ≈ **20** XP (`debug-465916.log` line 3).
- **Energy costs**: bot match = **20** energy; basic drill = **10**.

So a bot match often yields **~same XP** as a drill while costing **2× energy**, even before drill targeting advantages.

### “After 2 battles I have to wait hours.”

- Regen: **1 energy / 6 min** → **20 energy = 120 minutes** to recover (`debug-465916.log` line 7).
- Two bot battles is 40 energy → ~**4 hours** to fully regen that spend if starting from 0.
- Additionally, energy caps at 100, so “overnight regen” beyond full is wasted; players who log in at full still face the same per-action costs.

### “Coins are scarce, refills feel forced.”

Current refills:
- **+50 energy**, costs **200/400/600**, max **3/day**
- If energy gates are too tight, refills become mandatory for basic play — which feels bad even if the economy is mathematically stable.

### “Evolution cooldown of 10 hours is too slow.”

Evolution start is constrained by:
- **10h cooldown** (hard-coded)
- **3 simultaneous evolutions** max (hard-coded)

This is a “momentum killer” because it blocks the *intended* progression path (evolutions) on a clock unrelated to player effort.

---

## 3) Designer Analysis (why it feels punishing)

### Confirmed from baseline evidence

- **CONFIRMED**: Drill XP collapses at mid-levels while XP per level keeps rising (lines 2–3).
- **CONFIRMED**: Bot match XP per card is comparable to drill XP at common levels, but costs 2× energy (lines 3–4).
- **CONFIRMED**: Current regen makes each 20-energy action equate to ~2 hours of downtime if you want to “earn it back” (line 7).
- **CONFIRMED**: Evolution cooldown is hard-coded 10h and not tunable from `game_config` (line 6 + migration audit).

### Design consequence

Players hit **hard walls** (energy + cooldown) before they hit “I’m satisfied for today”. That’s the opposite of a healthy stamina loop, which should end in “I’m done” more often than “I’m blocked”.

---

## 4) Proposed Rebalancing Strategy (config-driven)

### Summary table (current → proposed)

| Lever | Current | Proposed | Why |
|---|---:|---:|---|
| **Energy regen** | 1/6 min (10/h) | **1/4 min (15/h)** | Cuts downtime; supports 20–30 min session daily without refills feeling mandatory |
| **Bot battle energy** | 20 | **15** | Improves match frequency; narrows “XP-per-energy” gap vs drills |
| **Basic drill XP base** | 30 | **50** | Makes early drills visibly move the bar |
| **Advanced drill XP base** | 80 | **120** | Keeps drills meaningful at midgame after diminishing returns |
| **Evolution cooldown** | 10h (hard-coded) | **6h** (from config) | Reduces “one evolution per day” feel; keeps anti-bot intent |
| **Max active evolutions** | 3 (hard-coded) | **4** (from config) | Lets players “queue” progress; lowers frustration without removing pacing |
| **Energy refill costs/cap** | 200/400/600, max 3 | **unchanged for now** | First rebalance should reduce forced refills before touching sinks |

### Key principle

Instead of pushing *everything* up, focus on fixing the **relative imbalance**:
- Battles should be “fun and broadly rewarding”
- Drills should be “targeted and efficient”

Reducing bot energy to 15 + raising regen to 1/4 min makes battles more playable. Raising drill XP bases makes drills feel worthwhile at mid levels without breaking match XP caps.

---

## 5) Simulated Progression Curves (simple model)

### Assumptions (explicit)

- We model one “focus card” in the starting XI.
- Daily routine:
  - **Casual**: 2 bot matches (wins) + 5 drills (on focus card)
  - **Hardcore**: 5 bot matches + 5 drills + 1 fusion (if available)
- Match XP per card uses a representative **bot win at rating ~6**:
  - Baseline bot win @6.0 ≈ **19 XP** per card (`debug-465916.log` line 4).
- Drill XP uses baseline diminishing formula with proposed bases.

### Current (baseline) – focus card XP/day

- At **Level 10**:
  - 5 basic drills: \(5 \times 20 = 100\) XP
  - 2 bot wins: \(2 \times 19 = 38\) XP
  - **Total ≈ 138 XP/day** vs **277 XP** to level → ~**2 days/level**
- At **Level 25** (advanced drills assumed):
  - 5 advanced drills: \(5 \times 36 = 180\) XP
  - 2 bot wins: \(38\) XP
  - **Total ≈ 218 XP/day** vs **1517 XP** → ~**7 days/level**

This aligns with the “glacial midgame” feeling even for engaged daily play.

### Proposed – focus card XP/day (same play, new numbers)

At Level 25, advanced base 120 gives:
- \(xp = \lfloor 120/(1+0.05\cdot 24)\rfloor = \lfloor 120/2.2\rfloor = 54\)
- 5 drills: \(270\) XP
- Matches unchanged (unless we also tune match XP later): \(+38\)
- **Total ≈ 308 XP/day** vs **1517 XP** → ~**5 days/level**

This is a meaningful improvement without “max in weeks”.

---

## 6) Risks & Mitigations

- **Risk: coin inflation** from more matches/day (if energy is less binding).
  - **Mitigation**: keep coin rewards unchanged initially; monitor ledger and adjust `match_bot_*` via `game_config`.
- **Risk: players progress too fast early** if drill XP increases.
  - **Mitigation**: diminishing returns already compresses late-game; keep match XP caps (100/day per card) intact.
- **Risk: UI mismatch continues** (hardcoded “10 energy”/“20 energy” copy).
  - **Mitigation**: refactor UI to read and display `game_config` values, same as RPC uses.
- **Risk: evolution pacing too loose** (6h + 4 slots).
  - **Mitigation**: keep costs the same; keep replacement rule; tune with config if needed.

---

## 7) Implementation Plan (SDD + production-safe)

### A) Config keys (add to `game_config`)

Add (new) keys:
- `energy_regen_per_min` (update default to **0.25**)
- `match_energy_bot` (update default to **15**)
- `drill_basic_xp` (update default to **50**)
- `drill_advanced_xp` (update default to **120**)
- `evolution_cooldown_hours` (**6**)
- `evolution_max_active` (**4**)

### B) RPC updates (Supabase)

- Update `sync_action_energy` to use `energy_regen_per_min` as today (already does).
- Update `start_player_evolution` to use:
  - `evolution_cooldown_hours` (instead of hard-coded 10)
  - `evolution_max_active` (instead of hard-coded 3)
- Leave drill XP math unchanged, only adjust the `drill_*_xp` config seeds.

### C) Bot refactors (Discord app layer)

- Replace all hardcoded UI strings (“Bot battles consume 20”, “Cost 10 Energy”, etc.) with values fetched from `game_config`.
- Ensure drill previews use the same config bases (`drill_basic_xp`, `drill_advanced_xp`) the RPC uses.
- Remove any remaining hardcoded energy costs in embeds.

### D) `/debug energy` admin command

- Slash command `/debug energy` for bot owner/admin only:
  - Shows: `energy_max`, `energy_regen_per_min`, computed “minutes per energy”, match/drill costs, refill costs/cap.
  - Provides a small simulator: given current energy and a delta minutes (e.g. +30m), show expected regen and “time to full”.

### E) Verification

- Apply migration locally; run `supabase/scripts/verify_required_schema.sql`.
- Run `pytest`.
- Manual persona walkthrough:
  - New user → `/battle hub` energy cost text matches real deduction.
  - Level 10 player → drill XP is visibly higher; bot battles no longer feel “worse than drills”.

