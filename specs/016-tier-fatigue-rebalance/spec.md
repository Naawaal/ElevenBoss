# Feature Specification: Division-Tier Fatigue & Injury Rebalance

**Feature Branch**: `016-tier-fatigue-rebalance`

**Created**: 2026-07-13

**Status**: Implemented

**Input**: User description: "Rebalance fatigue drain, daily recovery, injury chance, and hospital recovery by Division Rank intensity tier (forgiving at low divisions, demanding at top). Add UI transparency (Hospital intensity header, injury math on profile, pre-match fatigue warning). Fair hospital backfill + one-time fatigue floor. Defer squad soft-lock emergency fillers. AI opponents and cup matches use the manager's intensity tier. Intensity tier updates only on Monday weekly rollover, not mid-week LP climbs."

## Background & Motivation

ElevenBoss fatigue and injury are **technically functional but economically punishing** for Discord retention: multi-day waits and forced rotation of low-attachment squads kill daily engagement. Prior patches (011 QoL, 012 fair ETA) compressed clocks globally, but a single global curve still over-punishes learners and under-differentiates champions.

Industry peers separate difficulty by context:

| Title | Relevant lesson | Flaw if copied blindly |
|-------|-----------------|------------------------|
| Football Manager | Lower leagues = lighter schedules / lower expectations | Too much micromanagement for Discord |
| EA FC Career Mode | Match congestion + intensity drive fatigue; higher divisions = more pressure | In-game days ≠ Discord real days |

**ElevenBoss approach:** Keep the same systems (match drain, daily passive, injury rolls, Hospital, Recovery Session). Scale **intensity** by the club’s **Division Rank** so Grassroots/Amateur stay forgiving while Elite/Legendary demand rotation and facilities. Make the curve **visible** in Hospital, profile injury copy, and pre-match warnings. Ship a **fair one-time backfill** so current patients are not stranded on old clocks.

## Intensity Tiers (Division Mapping)

Six live divisions map to three intensity tiers (**2-2-2 split**):

| Intensity tier | Divisions | Match fatigue base drain | Daily natural recovery base | Injury base chance | Moderate hospital base days | Difficulty vibe |
|----------------|-----------|--------------------------|-----------------------------|--------------------|-----------------------------|-----------------|
| **Tier 1** | Grassroots, Amateur | **8** | **+35** | **0.25%** | **3 days** | Forgiving; learn tactics |
| **Tier 2** | Semi-Pro, Professional | **12** | **+25** | **0.40%** | **5 days** | Start rotating squad |
| **Tier 3** | Elite, Legendary | **16** | **+15** | **0.60%** | **8 days** | Deep squad required |

Managers should feel a distinct jump when promoting **out of Amateur → Semi-Pro** and again **out of Professional → Elite**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lower Divisions Feel Playable Daily (Priority: P1)

As a Grassroots or Amateur manager, playing my main XI in a competitive match does not dump stars into deep fatigue, and daily natural recovery (plus Training Ground) keeps pace so I am not forced into multi-day benches just to stay match-fit.

**Why this priority**: Retention pain is strongest at the learning end of the ladder; this is the core product bet of the rebalance.

**Independent Test**: Place a club in Grassroots or Amateur; rest a starter at 100 fatigue; complete one competitive match on Neutral stance with a known PHY; confirm drain uses Tier 1 base **8** and the published PHY/tactic modifiers; after one daily recovery tick at a known TG level, confirm recovery uses Tier 1 base **+35** plus TG scaling.

**Acceptance Scenarios**:

1. **Given** a club on intensity Tier 1 (Grassroots or Amateur), **When** match fatigue drain is computed for a starter, **Then** the tier base component is **8** (not the previous global base of 18).
2. **Given** Drain = (Tier base − PHY × 0.10) + tactic modifier, **When** stance is Neutral / Attack / Defend, **Then** tactic modifiers are **0 / +4 / −2** respectively.
3. **Given** a Tier 1 club with Training Ground level 3, **When** daily natural recovery runs for a non-hospital card, **Then** fatigue increases by **35 + (3 × 2) = 41** (capped at 100).
4. **Given** a Tier 1 manager plays roughly one competitive match per day and receives daily recovery, **When** comparing to the pre-patch global curve, **Then** sustaining a high-fatigue XI is materially easier (qualitative: less forced multi-day rest solely for fitness).

---

### User Story 2 - Top Divisions Demand Rotation and Facilities (Priority: P1)

As an Elite or Legendary manager, matches drain more, daily recovery is tighter, injuries are more likely when tired, and Hospital stays (especially Moderate/Major) are longer unless my Hospital level shortens them—so facilities and squad depth matter at the top.

**Why this priority**: Without a harder top end, the forgiving bottom would flatten competitive differentiation.

**Independent Test**: Place a club in Elite or Legendary; compare drain, daily recovery, injury base chance, and Moderate untreated hospital days against Tier 1 published table; verify Hospital level still shortens stays via the published facility curve.

**Acceptance Scenarios**:

1. **Given** intensity Tier 3, **When** match fatigue drain is computed, **Then** the tier base component is **16**.
2. **Given** Tier 3 and TG level 3, **When** daily natural recovery runs, **Then** the bump is **15 + 6 = 21** (capped at 100).
3. **Given** Tier 3, **When** injury probability is computed before fatigue/age modifiers, **Then** the tier base chance is **0.60%** (Tier 1 uses **0.25%**; Tier 2 uses **0.40%**).
4. **Given** a Moderate injury at Tier 3 with no Hospital benefit, **When** recovery days are computed, **Then** the moderate base is **8 days** before facility shortening.
5. **Given** Final days = (tier moderate base × severity multiplier) / (1 + 0.2 × Hospital level), **When** severity is Minor / Moderate / Major, **Then** severity multipliers are **0.33 / 1.0 / 2.5** and days are never lengthened by Hospital (higher Hospital always ≤ lower Hospital for the same injury).
6. **Given** Moderate injury, Tier 3, Hospital level 5, **When** recovery is computed, **Then** expected stay is **4 days** (8 / (1 + 1.0)), illustrating top-end Hospital value.

---

### User Story 3 - Mid-Ladder Intensity Is a Clear Step Up (Priority: P2)

As a Semi-Pro or Professional manager, I experience the middle intensity band (drain 12, recovery +25 base, injury 0.40%, Moderate hospital base 5 days) so promotion out of Amateur and toward Elite feels like a planned difficulty step, not a surprise cliff.

**Why this priority**: Completes the 2-2-2 curve; smaller than P1 but required for a coherent ladder.

**Independent Test**: Club in Semi-Pro or Professional; verify Tier 2 table values for drain, recovery, injury base, and Moderate hospital base.

**Acceptance Scenarios**:

1. **Given** Tier 2, **When** drain / daily recovery base / injury base / Moderate hospital base are read from the published table, **Then** they are **12 / +25 / 0.40% / 5 days**.
2. **Given** the same player card and stance, **When** comparing Tier 1 vs Tier 2 vs Tier 3 drain bases only, **Then** drain bases strictly increase 8 → 12 → 16.

---

### User Story 4 - Hospital and Injury UI Explain Why It Feels Harder (Priority: P1)

As a manager, I can see my current league intensity and how it affects Hospital recovery and an injured player’s expected return, so longer waits at the top feel intentional—not broken.

**Why this priority**: Transparency is required for acceptance of tiered difficulty; without it, Tier 3 feels like a bug.

**Independent Test**: Open `/store` → Facilities Hospital panel on each intensity tier; open an injured player’s profile; confirm intensity header and recovery math breakdown copy.

**Acceptance Scenarios**:

1. **Given** I open the Hospital / Medical Center panel under Club Facilities, **When** my intensity tier is Tier 3 (Elite or Legendary), **Then** I see a clear intensity indicator (e.g. High / Legendary-class) and copy that base recovery is longer than lower leagues.
2. **Given** Tier 1, **When** I open the same panel, **Then** intensity copy reflects a forgiving / lower intensity—not the Tier 3 warning.
3. **Given** a player is injured, **When** I view their profile injury report, **Then** I see severity, expected return, and a short breakdown showing tier base days and facility shortening (e.g. base days at my intensity vs facility bonus).
4. **Given** no injury, **When** I view profile, **Then** no false injured recovery math is shown.

---

### User Story 5 - Pre-Match Warning for Heavily Fatigued Starters (Priority: P2)

As a manager about to start a competitive match, if any starters are heavily fatigued (below 30% fatigue), the match ticket / pre-match embed warns me that injury risk is elevated.

**Why this priority**: Prevents “gotcha” injuries; reinforces the fatigue → injury link without blocking the match.

**Independent Test**: Set 1+ starters below 30% fatigue; open pre-match battle flow; confirm warning with count; set all starters ≥ 30%; confirm warning absent.

**Acceptance Scenarios**:

1. **Given** three starters have fatigue **&lt; 30**, **When** I view the pre-match / match ticket embed for a competitive match, **Then** a warning states that those players are heavily fatigued and injury risk is high (count included).
2. **Given** all starters have fatigue ≥ 30, **When** I view the same embed, **Then** that heavy-fatigue warning is not shown.
3. **Given** the warning is shown, **When** I proceed to start the match, **Then** the match is not blocked solely by this warning (advisory only).

---

### User Story 6 - Fair Migration for Current Patients and Exhausted Squads (Priority: P1)

As a manager with players already in Hospital (or stuck at very low fatigue under the old global curve), when this rebalance ships I am not stranded on old longer clocks, and exhausted squads get a one-time rest floor so the new lower drains are immediately feelable.

**Why this priority**: Same fairness class as 012; shipping new math without migration recreates two classes of managers.

**Independent Test**: Seed an active hospital stay under old ETA; run fairness pass with new tier-aware formula crediting time served; seed a card at fatigue 10; confirm post-pass floor to at least 50 if uninjured.

**Acceptance Scenarios**:

1. **Given** an active hospital patient, **When** the one-time fairness pass runs, **Then** expected return is recalculated with the club’s intensity tier + severity + current Hospital level, minus days already served, and **never lengthened** vs the prior ETA.
2. **Given** days already served ≥ new total, **When** the pass runs, **Then** the player is discharged as recovered (injury cleared) the same way a normal on-time discharge would.
3. **Given** an uninjured player card with fatigue below 50, **When** the one-time rest pass runs, **Then** fatigue becomes **max(current, 50)**.
4. **Given** a card already at fatigue ≥ 50 or currently injured/in Hospital, **When** the rest floor pass runs, **Then** injured/hospital cards are not given a misleading “healthy rest” that conflicts with injury state (floor applies to eligible uninjured cards only).
5. **Given** the fairness pass is re-run, **When** stays are already aligned, **Then** it is idempotent (no further unjustified shortening beyond the formula).

---

### User Story 7 - Opponent and Cup Parity Use My Intensity (Priority: P2)

As a manager in a high intensity tier, bot opponents in my matches also feel the same attrition rules for that match, and cup matches do not give me an “easy fatigue break” by ignoring my primary league intensity.

**Why this priority**: Prevents exploiting cups or noticing AI that never tires while the human XI collapses.

**Independent Test**: Tier 3 club plays a bot competitive match and a cup match; confirm both sides’ fatigue/injury intensity for that match use the human club’s Tier 3 parameters.

**Acceptance Scenarios**:

1. **Given** I am Tier 3, **When** I play a bot opponent in a competitive match, **Then** fatigue drain / injury intensity for that match use **my** Tier 3 parameters for both sides (AI parity for that match).
2. **Given** I am Tier 3, **When** I play a cup match, **Then** fatigue/injury intensity still use my primary league intensity tier (no cup downgrade).
3. **Given** I am Tier 1, **When** the same flows run, **Then** both sides use Tier 1 parameters.

---

### Edge Cases

- **Promotion timing**: Intensity tier used for gameplay is updated on **Monday weekly Division Rank rollover** from the club’s settled division—not mid-week when LP briefly crosses a threshold. Mid-week “virtual” climbs do not instantly spike drain/injury.
- **Missing / unknown division**: Treat as Tier 1 (Grassroots-equivalent) so new or broken state stays forgiving.
- **Fatigue clamp**: Drain and recovery never push outside 0–100.
- **PHY extreme**: Very high PHY can reduce drain to 0 for a match; never negative drain that *adds* fatigue.
- **Friendlies**: Remain sandbox for competitive fatigue/injury writes unless an existing rule already applies; this feature does not newly punish friendlies.
- **Recovery Session**: Active Recovery Session (+40 fatigue, energy cost) remains available and is **not** retuned by this feature unless a later patch says otherwise.
- **Bench rest**: Competitive bench rest amount remains as currently shipped (post-011 +25) unless explicitly changed later; this feature’s recovery retune is the **daily natural** formula and match **drain** formula.
- **Squad soft-lock (cannot field 11 due to injuries)**: **Out of scope** for this feature. No emergency grey cards and no academy emergency filler. Document as a known edge case to **monitor post-launch** (expected rarer after global drain reduction + forgiving Tier 1).
- **Bot-controlled clubs**: When a bot club is the intensity “owner” of a match context, use that club’s intensity tier consistently; when simulating against a human, AI parity follows the human’s tier for that match (US7).
- **Double-apply migration**: Fairness and fatigue-floor passes must be safe if accidentally run twice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST map divisions to intensity tiers as: Tier 1 = Grassroots + Amateur; Tier 2 = Semi-Pro + Professional; Tier 3 = Elite + Legendary.
- **FR-002**: System MUST persist or otherwise resolve each club’s **effective intensity tier** for gameplay such that it updates on **Monday weekly Division Rank rollover** from settled division, and MUST NOT spike mid-week solely from intra-week LP movement.
- **FR-003**: Match fatigue drain MUST use  
  `Drain = (Tier_Base_Drain − (PHY × 0.10)) + Tactic_Modifier`  
  with Tier bases **8 / 12 / 16**, tactic modifiers Attack **+4**, Defend **−2**, Neutral **0**, result floored at 0.
- **FR-004**: Daily natural (non-hospital) fatigue recovery MUST use  
  `Recovery = Tier_Natural_Recovery + (Training_Ground_Level × 2)`  
  with tier bases **35 / 25 / 15**, capped at 100.
- **FR-005**: Injury probability MUST use tier base chances **0.25% / 0.40% / 0.60%** plus  
  `Fatigue_Modifier = (100 − Fatigue) × 0.03%`  
  plus the existing age (and any retained PHY) modifiers already used for injury risk, subject to existing eligibility soft-caps (e.g. only sufficiently fatigued starters; at most one injury per club per match) unless this feature explicitly retires a soft-cap.
- **FR-006**: Hospital / injury recovery days MUST use  
  `Final_Days = (Tier_Moderate_Base_Days × Severity_Multiplier) / (1 + 0.2 × Hospital_Level)`  
  with Moderate bases **3 / 5 / 8**, severity multipliers Minor **0.33**, Moderate **1.0**, Major **2.5**, and a minimum of 1 day when still injured (unless existing discharge rules say otherwise).
- **FR-007**: Hospital facility UI MUST show a dynamic intensity header/copy based on the club’s effective intensity tier.
- **FR-008**: Injured player profile MUST show expected return and a short tier-base + facility-bonus breakdown.
- **FR-009**: Competitive pre-match / match ticket UI MUST warn when any starter has fatigue &lt; 30, including a count; warning is advisory only.
- **FR-010**: One-time fairness pass MUST recalculate open hospital (and untreated overflow, if still applicable) recovery using the new tier-aware formula, credit time served, never lengthen, and early-discharge when served past the new total.
- **FR-011**: One-time pass MUST set eligible uninjured cards’ fatigue to `max(current, 50)`.
- **FR-012**: Bot opponents in a match against a human MUST use that human’s intensity tier for fatigue drain and injury intensity for that match; cup matches MUST use the manager’s primary league intensity tier.
- **FR-013**: No new slash commands or hubs; extend existing `/store` Facilities, player profile, and `/battle` pre-match surfaces only.
- **FR-014**: This feature MUST NOT implement emergency youth/grey “soft-lock fillers”; soft-lock remains a monitored edge case only.
- **FR-015**: Player-facing changelog MUST describe the tiered intensity curve and migration fairness when the feature ships.

### Key Entities

- **Intensity tier**: One of three bands (1–3) derived from Division Rank via the 2-2-2 mapping; effective value used by drain, recovery, injury, and hospital math.
- **Tier balance table**: Published bases for drain, daily recovery, injury chance, and Moderate hospital days per intensity tier.
- **Injury recovery window**: Calendar expected return from severity × tier moderate base ÷ Hospital curve.
- **Fairness migration**: One-time recalculation of open injury clocks + uninjured fatigue floor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tier 1 match drain base is **8**; Tier 3 is **16**; Tier 2 is **12**.
- **SC-002**: A Tier 1 club at TG 3 gains **+41** fatigue from one daily natural tick (pre-cap).
- **SC-003**: A Tier 3 Moderate injury at Hospital level 5 expects **4** days recovery under the published formula.
- **SC-004**: Managers can identify their intensity band from Hospital UI without asking support (spot-check: correct copy for Tier 1 vs Tier 3).
- **SC-005**: Pre-match warning appears iff ≥1 starter has fatigue &lt; 30 and includes an accurate count.
- **SC-006**: After migration, no open hospital ETA is later than it was before the pass; cards that have fully “served” the new total are discharged.
- **SC-007**: After migration, every eligible uninjured card has fatigue ≥ 50.
- **SC-008**: Qualitative: fewer “can’t play my XI / hospital forever” complaints from Grassroots–Amateur managers; Elite–Legendary managers still cite rotation and Hospital as meaningful (post-launch monitor).

## Assumptions

- Division names remain the live six: Grassroots, Amateur, Semi-Pro, Professional, Elite, Legendary (proposal’s Bronze/Silver/Gold/Platinum labels map onto this ladder via the locked 2-2-2 split).
- “Season” language in the proposal is interpreted as **Monday weekly Division Rank rollover** for intensity updates—the cadence already used for settled division changes—not a rarer true-season-only lock.
- Age modifier for injury remains the existing progression (age above ~30 increases risk); PHY resistance modifier may remain if already live. The proposal’s explicit new pieces are tier base + fatigue modifier at **0.03% per missing fatigue point**.
- Match “intensity” surcharge from older drain formulas (flat +5) is **absorbed/removed** in favor of the published tier-base + tactic formula unless planning proves a retained flag is required for an existing mode.
- Hospital bed capacity, upgrade costs, Recovery Session grant/cost, fatigue **performance penalty bands**, and bench rest **+25** are unchanged except where FR-001–FR-015 apply.
- Friendlies stay non-punitive for competitive fatigue/injury writes.
- Soft-lock inability to field 11 is statistically rarer after this curve; no filler system in this release.
- AI parity means shared **intensity parameters** for that match, not identical RNG outcomes.

## Out of Scope

- Emergency grey cards or academy emergency promotion to break injury soft-locks.
- New Medical Center slash command or separate Hospital hub.
- Instant heal / fatigue Store consumables.
- Redesigning Division Rank promotion/relegation rules themselves (only consuming settled division for intensity).
- Retuning Recovery Session, action energy, match XP/coins, or Training Ground upgrade costs.
- Changing Youth Academy intake/growth (015) except documenting soft-lock as a future monitor item that must not silently couple here.
- Mid-week live LP → instant intensity spikes.
