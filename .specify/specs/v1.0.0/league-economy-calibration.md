# League Economy Calibration Document (US-26)

**Status:** Audit complete — coded values vs. design assumptions, exploit vectors, calibrated targets.  
**Evidence:** `python scripts/simulate_league_economy.py` (pure formulas from `packages/economy/economy/flows.py`, `032_league_mode_v2.sql`).  
**Date:** 2026-07-07

---

## 1. Executive Summary

The implemented league system is **coin-only** (no gems, no player cards, no season-end XP bonus). Total injection for a Grassroots champion over one 4-week season is **~7,150 coins** (match + prize + milestones) — slightly **below** the audit’s assumed 7,800 but with a **different split** (higher per-match, lower season prize than assumed 5,000 for 1st).

**Verdict:** League is an **additive faucet** on top of bot/daily income. It does **not** currently break the hardcore sink budget (hardcore remains deeply net-negative over 28 days). It **does** create two real risks:

1. **Auto-sim energy bypass** — expired fixtures pay full match coins + XP with **0 energy** (`active_player_id=None`).
2. **Triple coin faucet** — per-match coins + season pool + matchday milestones with **no entry fee** (`entry_fee_coins` in admin config is **not enforced** on registration).

Progression risk is moderate: league XP uses **1.25×** multiplier on all 11 cards per match, subject to **100 XP/card/day** cap — no season-end XP lump sum exists in code.

---

## 2. Coded Reward Table (Source of Truth)

### 2.1 Per-match coins

| Division     | Win | Draw (win÷3) | Loss |
|-------------|-----|--------------|------|
| Grassroots  | 300 | 100          | 0    |
| Amateur     | 340 | 113          | 0    |
| Semi-Pro    | 380 | 126          | 0    |
| Professional| 420 | 140          | 0    |
| Elite       | 460 | 153          | 0    |
| Legendary   | 500 | 166          | 0    |

- **Config keys:** `match_league_win_min` (300), `match_league_win_max` (500) — `028_economy_foundation.sql` / `flows.py`
- **Pipe:** `apply_club_economy` via `apply_league_human_rewards` (`league_rewards.py`)
- **Energy:** 10 `action_energy` when human triggers play; **0 on auto-sim** (`deduct_energy=False`)

### 2.2 Season-end prizes

| Position | Share | Coins (pool=5000) | Award type      |
|----------|-------|-------------------|-----------------|
| 1st      | 60%   | **3,000**         | champion        |
| 2nd      | 25%   | **1,250**         | runner_up       |
| 3rd      | 10%   | **500**           | third           |
| 4th–8th  | flat  | **200** each      | participation   |

- **Config:** `league_season_prize_pool_base` = 5000, `league_participation_coins` = 200
- **RPC:** `distribute_season_prizes(p_season_id)` — `032_league_mode_v2.sql`
- **No gems, cards, or XP** in season awards

### 2.3 Matchday milestones

| Threshold | Bonus | Config key |
|-----------|-------|------------|
| 6+ pts in matchday | 150 coins | `league_milestone_pts_threshold`, `league_milestone_bonus_coins` |

- Max ~7 matchdays per 8-club season → up to **1,050** bonus if threshold hit every matchday (optimistic; **450** assumed in simulations = 3 hit)

### 2.4 Match XP (not coins)

- `match_type='league'` → **1.25×** base (`MATCH_TYPE_MULT` in `progression.py`)
- All 11 squad cards receive XP via `process_match_result`
- **Daily cap:** 100 XP/card/day (`027_progression_hardening.sql`)
- **No season-end XP bonus** in current implementation

### 2.5 Audit assumption vs. coded reality

| Audit assumed | Coded actual | Flag |
|---------------|--------------|------|
| 1st: 5,000 coins | 3,000 season + ~3,700 match (12W) | Different split; total ~7,150 |
| Gems (200/100/50) | **None** | Missing feature |
| Epic/Rare/Common cards | **None** | Missing feature |
| Season +200 XP/player | **None** | Missing feature |
| Flat 200/win all divisions | 300–500 by division | Higher at top divisions |
| Entry fee 2,000 | **Config only, not charged** | **Exploit gap** |

---

## 3. Four-Week Season Simulations (Grassroots, 14 fixtures)

Run: `python scripts/simulate_league_economy.py`

| Archetype | Record | Match coins | Season prize | Milestones (3×) | **League total** | Energy (manual) |
|-----------|--------|-------------|--------------|-----------------|------------------|-----------------|
| Champion  | 12W-1D-1L | 3,700 | 3,000 | 450 | **7,150** | 140 |
| Mid (3rd) | 7W-4D-3L | 2,500 | 500 | 450 | **3,450** | 140 |
| Bottom    | 3W-3D-8L | 1,200 | 200 | 450 | **1,850** | 140 |

### 3.1 Combined with 28-day baseline (league is **additive**)

League fixtures do **not** replace bot match daily cap — they are extra scheduled matches.

| Archetype | Casual 28d baseline | + League season | **Combined** |
|-----------|---------------------|-----------------|--------------|
| Champion  | 0 | +7,150 | **+7,150** |
| Mid       | 0 | +3,450 | **+3,450** |
| Bottom    | 0 | +1,850 | **+1,850** |

| Archetype | Hardcore 28d baseline | + League (champion) | **Combined** |
|-----------|----------------------|---------------------|--------------|
| Hardcore max spender | -77,840 | +7,150 | **-70,690** (still negative) |

**Interpretation:** League softens hardcore coin drain but does **not** flip the economy positive for max-activity players. Casual/mid players gain meaningful savings (+3k–7k/season).

### 3.2 Auto-sim scenario (0 energy, full rewards)

| Archetype | Coins earned | Energy |
|-----------|--------------|--------|
| Champion (all auto-sim) | 7,150 | **0** |
| Mid | 3,450 | **0** |
| Bottom | 1,850 | **0** |

**Risk:** Passive managers who ignore fixtures still receive full faucet — undermines energy as gate.

---

## 4. Exploit & Balance Risk Matrix

| ID | Risk | Severity | Evidence | Status |
|----|------|----------|----------|--------|
| E1 | Auto-sim = free coins + XP | **High** | `auto_sim_expired_fixtures` → `active_player_id=None` → `deduct_energy=False` | Open |
| E2 | Entry fee not charged | **High** | `entry_fee_coins` in `SeasonConfigModal` only; no `league_cog` wiring | Open |
| E3 | Triple coin faucet (match + prize + milestone) | **Medium** | Three `apply_club_economy` sources per season | By design; tune pool |
| E4 | Alt-account collusion | **Medium** | No club-age / min-matches gate on join | Open |
| E5 | OVR cap config only | **Low–Med** | Admin `ovr_cap` in config_json; not validated at match start | Open |
| E6 | All 11 cards league XP every match | **Medium** | No rotation cap; 1.25× mult | Mitigated by 100 XP/day cap |
| E7 | Winner-stays-rich (multi-season) | **Medium** | Coins compound; no division prize scaling yet | Partial (divisions exist for match pay) |
| E8 | Disband mid-season | **Low** | Forfeit 3-0; prizes by final active standings | Implemented |
| E9 | Exclusive cards sold on market | **N/A** | No card prizes shipped | — |

---

## 5. Calibrated Target Values (Recommended)

Goals: (a) league feels rewarding, (b) net injection ≤ ~5,000 coins/season for champion at Grassroots, (c) close auto-sim exploit, (d) add coin sink at entry.

### 5.1 Proposed `game_config` changes

| Key | Current | **Proposed** | Rationale |
|-----|---------|--------------|-----------|
| `league_season_prize_pool_base` | 5000 | **3500** | −30% season injection; shift prestige to trophies |
| `league_participation_coins` | 200 | **150** | Slight cut for 4th–8th |
| `league_milestone_bonus_coins` | 150 | **100** | Milestones still engage; −33% |
| `match_league_win_min` | 300 | **250** | Reduce per-match double-dip |
| `match_league_win_max` | 500 | **400** | Legendary still best tier |
| `league_entry_fee_coins` | *(new)* | **1500** | Sink at registration; refund on season complete |
| `league_auto_sim_coin_mult` | *(new)* | **0.5** | Auto-sim earns 50% match coins (prizes unchanged) |

**Projected champion total (12W, 3 milestones, Grassroots, manual play):**

- Match: 12×250 + 100 = **3,100** (was 3,700)
- Prize: **2,100** (was 3,000)
- Milestones: **300** (was 450)
- Entry fee: **-1,500** (refundable) or sunk if quit
- **Net: ~3,900** manual / **~3,450** if 50% matches auto-simmed

### 5.2 Features to implement (not config-only)

| Mitigation | Implementation |
|------------|----------------|
| Entry fee | Charge `apply_club_economy(-fee, 'league_entry', ...)` on `league_participants` insert; refund RPC on season end if `is_active` |
| Auto-sim coin mult | Pass `coin_mult=0.5` when `deduct_energy=False` in `apply_league_human_rewards` |
| XP season bonus | **Defer** — audit assumed it; not shipped; if added, cap to top 5 appearances × level-scaled amount |
| Untradeable league cards | **Defer** until card prizes exist |
| Club-age gate | `matches_played >= 10` AND account age ≥ 7 days before join |
| Division-scaled entry fee | `1500 + 250 × division_tier` |

### 5.3 What we are **not** recommending

- **Removing per-match league coins entirely** — players expect immediate feedback; season-only prizes feel invisible.
- **Double energy on league matches** — conflicts with auto-sim policy; prefer separate mult or league-energy bar later.
- **Matching audit’s 5,000 coin 1st prize** — would push champion injection to ~9k+ with current match pays.

---

## 6. Progression (XP) Impact

Per starter playing all 14 league matches (win, rating ~7.0):

- ~18–22 XP/match × 1.25 league mult ≈ **~280–320 XP/season** per card (under daily cap if spread across days)
- Skill points from levels gained: depends on level; at level 10, ~2–3 levels/season possible for young squad — **acceptable** with POT cap
- **No season-end XP bomb** in code — audit Q2 risk is **lower than assumed**

---

## 7. Monitoring Metrics & Alert Thresholds

Run weekly via SQL / `scripts/simulate_economy.py` + ledger queries.

| Metric | Query / source | Green | Yellow | Red (auto-review) |
|--------|----------------|-------|--------|-------------------|
| League coin injection / season | `SUM(amount) FROM economy_ledger WHERE source LIKE 'league%'` per season | < 40k guild-wide (8 clubs × ~5k) | 40–55k | > 55k |
| Auto-sim share of league matches | `match_runs` where `active_player_id IS NULL` / total league runs | < 30% | 30–50% | > 50% |
| Avg club coins (league participants) | `players.coins` join `league_participants` | +5% vs non-participants | +5–15% | > +15% WoW |
| Median squad OVR growth (league) | snapshot `player_cards` OVR week-over-week | < +1.5/mo | +1.5–2.5 | > +2.5 |
| Milestone claim rate | `league_matchday_milestones.milestone_claimed` | 40–70% | < 40% or > 80% | > 90% (too easy) |
| Entry fee collection | ledger `league_entry` | 100% of humans joined | — | < 100% (bug) |

**Adjustment playbook (yellow/red):**

1. Lower `league_season_prize_pool_base` by 500
2. Raise `league_entry_fee_coins` by 250
3. Lower `league_auto_sim_coin_mult` by 0.1
4. No Discord admin command — edit `game_config` + announce in `change_log.md`

---

## 8. Answers to Audit Questions (Q1–Q7)

| Q | Summary answer |
|---|----------------|
| **Q1** Too many coins vs sinks? | **Moderate risk** for casual/mid; **low** for hardcore. Main issue is additive faucet + no entry fee, not absolute champion total. |
| **Q2** Double-dip XP/OVR? | **Lower risk than assumed** — no season XP bonus; daily 100 XP cap applies. Watch 11-card full-squad XP. |
| **Q3** Veteran vs newcomer gap? | **Medium** — coin compounding + no promotion/relegation prize tiers yet. Participation 200 coins helps slightly. |
| **Q4** Alt collusion? | **Medium** — no age/activity gates; match-fixing hard to detect. Recommend min matches + club age. |
| **Q5** Mid-season disband? | Prizes follow final standings; disbanded clubs forfeit fixtures. No reward for inactive. |
| **Q6** Energy respect? | **Split policy** — manual costs 10; auto-sim costs 0. **Needs calibration** (E1). |
| **Q7** Exclusive cards too strong? | **N/A** — not implemented. When added: bind to club, no market listing. |

---

## 9. Implementation Checklist (post-audit)

**Tracked as US-27** — see `.specify/specs/v1.0.0/spec.md` AC-27, `plan.md` §25, `tasks.md` T27.

- [x] Migration `033_league_economy_calibration.sql` — new `game_config` keys + `league_participants.entry_fee_paid`
- [x] RPC `charge_league_entry_fees` + refund in `distribute_season_prizes`
- [x] Wire entry fee on season start in `admin_cog.py`
- [x] Auto-sim coin multiplier in `apply_league_human_rewards`
- [x] Club-age / matches-played join gate in `league_cog.py`
- [x] Update `change_log.md` when shipping
- [x] Re-run `scripts/simulate_league_economy.py` after config change

---

## 10. References

| File | Role |
|------|------|
| `packages/economy/economy/flows.py` | Coin formulas |
| `apps/discord_bot/core/league_rewards.py` | Match + milestone application |
| `apps/discord_bot/core/economy_rpc.py` | `apply_club_economy` pipe |
| `supabase/migrations/032_league_mode_v2.sql` | Prizes RPC, milestone table |
| `packages/player_engine/player_engine/progression.py` | League XP 1.25× |
| `scripts/simulate_league_economy.py` | Reproducible season math |
