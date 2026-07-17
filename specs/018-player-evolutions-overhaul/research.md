# Research: Player Evolutions Overhaul (018)

**Date**: 2026-07-14  
**Purpose**: Pre-integration assessment — audit ElevenBoss today, learn from FCM peers, PM/user lens, design blueprint for Speckit plan.

---

## 1. Audit — Current ElevenBoss implementation

### Surfaces (Discord)

| Surface | Behavior |
|---------|----------|
| `/development` → **Evolutions** | Hub: Browse Tracks, My Active, Start, Claim, Cancel |
| `/player-profile` | Shortcuts into evolution start/claim for focused card |
| Match pipeline | `process_match_result` → `tick_evolution_match_progress` (do not double-tick friendlies) |

### Data & RPCs

| Asset | Role |
|-------|------|
| `active_evolutions` | Club–card–track assignment, progress, status |
| `start_player_evolution` | Slot check, costs, insert active row |
| `claim_evolution_reward` | Apply rewards, complete row |
| `cancel_player_evolution` | Fee + status cancel |
| `tick_evolution_match_progress` | Increment progress for evolved XI (match results) |
| `game_config` keys | `evolution_max_active`, cooldown hours, costs (seeds may **drift** from hub) |

### Hardcoded tracks (placeholder-grade catalog)

Source: `packages/player_engine/player_engine/evolution_tracks.py` (SQL mirrors in evolutions migrations):

| Track ID | Goal | Reward | Min level |
|----------|------|--------|-----------|
| `pace_boost` | 3 matches | +5 PAC | 5 |
| `shooting_star` | 3 matches | +5 SHO | 10 |
| `def_wall` | 3 matches | +5 DEF | 8 |

Package constants: `MAX_ACTIVE_EVOLUTIONS = 3`, cooldown **10h**, start **25 energy** + `500 + 5×OVR` coins, cancel **100** coins. Non-repeatable. No goals/rating/assists metrics yet.

### Interaction with other progression

| System | Interaction |
|--------|-------------|
| Drills / Recovery / Fusion | **Blocked** while card has active evolution |
| Agent sale / P2P list | **Blocked** (062 peer guard) |
| Skill allocate / Mentor | Separate; evo claim must not invent SP |
| XP / leveling | Claim today is **stat bump**, not XP; must stay off ad-hoc XP |
| POT / OVR | Claim must clamp to potential; risk if rewards ignore POT |
| Fatigue / injury | UI may gate start; RPC parity needs verification |
| PlayStyles | Claim grants **stats only**; `/development` hub copy still says “evolve playstyles” (trust debt) |

### Known debt (must fix in overhaul)

1. **Config drift**: hub/Python ~3 slots / ~10h cooldown vs `game_config` seeds that may say 4 / 6h.  
2. **Copy lie**: PlayStyle language without grants.  
3. **Cost drift**: hub text vs `500+5×OVR` / RPC.  
4. **Catalog drift**: tracks hardcoded in two places (package + SQL).  
5. **Injury/eligibility**: start gates must be identical in UI and RPC.

---

## 2. Competitive research (FCM peers)

### EA Sports FC / FUT Evolutions

- **Objective stages** with visible progress (matches, goals, assists, wins in modes).  
- **Claim between stages**; incomplete objectives do not auto-pay.  
- **Slot limits** and time-limited EVO catalogs (FOMO).  
- Rewards: **OVR bumps, PlayStyles+, roles** — often with **eligibility caps** (max OVR to enter).  
- Some evolved players become **untradeable** (FUT market integrity) — ElevenBoss equivalent is soft lock while *active*, not forever.

**Takeaways**: Clear objectives; multi-stage optional; eligibility caps prevent stacking broken cards; Progressive UI; don’t pay rewards until claim.

### Football Manager

- Development via **training attributes, playing time, mentoring** — not discrete “Evo cards.”  
- Narrative: personality + playing time → growth; fewer discrete “missions.”

**Takeaways**: Playing-time gate feels fair; avoid too many arbitrary time-gates if match play is already scarce on Discord.

### Top Eleven / mobile FCM

- Short **missions / training programs** with slot limits; rewards are attribute or item bumps.  
- Monetization FOMO exists — ElevenBoss should stay **F2P fair**, time-bounded only via match play + cooldown.

**Best practices to borrow**

| Practice | Apply how |
|----------|-----------|
| Visible objective + reward preview | Hub embeds + progress bars |
| Slot scarcity (3) | Keep 3; kill config drift |
| Eligibility (level / OVR band) | Keep min level; add max OVR/POT safety |
| Claim ritual | Keep explicit claim (idempotent) |
| Mix rewards | Stats now; PlayStyles phased after truthfulness |
| Soft lock while active | Keep blockers; message like transfer conflicts |

**Avoid**

- Weekly paid meta that invalidates free tracks.  
- Objectives that require unavailable match types.  
- Rewards that ignore POT / devalue drills+fusion.

---

## 3. User & PM perspective

### Manager excitement

- “This CB can become my wall” narrative.  
- Progress after real matches (agency).  
- Tangible permanent reward.

### Manager frustration

- Wrong cost / wrong slot count.  
- Hub promises PlayStyle, claim only +1 PAC.  
- Card stuck in evo, can’t drill or list, unclear how to cancel.  
- Cooldown feels like a second jail after cancel.

### PM risks

| Risk | Mitigation |
|------|------------|
| OVR inflation | Reward clamps + eligibility max OVR; small deltas |
| Devalue drills/fusion | Evolutions = sparse narrative bump; drills = daily grind |
| Break transfer market | Keep list/sale blocks on active evo |
| Slot vs engagement | 3 slots; cooldown replaces 4th; cancel frees with fee |
| XP double-dip | No XP on claim unless via `apply_card_xp` by design |

### Balancing 3 slots with training/matches

- Evolutions should **consume** match appearances (alignment with league/bot matches), not compete for the same energy as drills on the *same* day as hard as a soft exclude: you choose who is “on program.”  
- Recovery Session remains available for fatigue on **non-locked** cards — managers rotate who is evolving.

---

## 4. Design blueprint (for `/speckit.plan`)

### Core mechanics

- **3 active slots** per club (single-sourced `game_config` + package defaults).  
- Each assignment: `track_id`, `card_id`, `progress`, `goal`, `status`.  
- Objectives: v1 **matches**; catalog may add goals / average rating later.  
- Start cost: energy + coins via economy pipe.  
- Cancel: fee + cooldown rules published.  
- Cold-start cooldown between *new* starts when no replacement.

### Rewards

- **P1**: Permanent stat boost clamped by POT / track cap.  
- **P2**: Optional PlayStyle grant into `player_playstyles` + match engine consume.  
- No free SP / coins on claim unless explicitly designed as sink-safe.

### Integration — where “evo cards” come from

- Not separate items: **any eligible owned card** enters a track.  
- Track catalog: migrate to **seed table** or shared module consumed by SQL + Python.  
- History: keep `active_evolutions` (+ optional completed archive view).

### UI/UX

- Hub under `/development` Evolutions:  
  - Slots `used/3`, cooldown timer, coin/energy, Browse / Active / Claim / Cancel.  
  - Progress bar text: `2/3 matches`.  
  - Reward preview matching claim.  
- Profile shortcuts remain.

### Database / backend (expected)

| Change | Why |
|--------|-----|
| Align config seeds to 3 / published cooldown | Kill drift |
| Optional `evolution_tracks` table | Data-driven catalog |
| Fix `claim_evolution_reward` for PlayStyles or remove copy | Truth |
| Harden start eligibility in RPC | Injury/lock parity |
| Feature flag or phased config | Rollout |

### Rollout

1. Spec/plan/tasks freeze slot=3 and cost formulas.  
2. Migration: config normalize; optional track table; PlayStyle path or copy fix.  
3. Flag/config: soft enable new tracks.  
4. Back-compat: existing active rows keep progress; remapped IDs if renamed.  
5. Verify schema + QA scripts for claim/race/cancel.

---

## 5. Decisions for plan (open → resolve in plan.md)

| Topic | Recommendation |
|-------|----------------|
| Max slots | **3** (override config seed 4) |
| PlayStyles in v1 overhaul | Fix copy first; grant PlayStyles in P2 milestone |
| Match types that tick | League + bot (+friendly only if intentional; avoid double-tick bug) |
| Repeatable tracks | Default **no** per card+track |
| Feature flag | Config key `evolution_overhaul_enabled` or track-table versioning |

---

## 6. References (code anchors)

- `packages/player_engine` evolution tracks / helpers  
- `apps/discord_bot/cogs/development_cog.py` Evolutions hub  
- Migrations: `020`/`023`/`038`/`046` evolutions; `062` peer guards  
- Match: `tick_evolution_match_progress` from `process_match_result`
