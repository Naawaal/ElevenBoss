# Feature Specification: Drill Attribute Boost

**Feature Branch**: `036-drill-stat-boost`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "Modify the training drill system so that, in addition to XP, each drill also grants +1 to the specific attribute being trained (e.g., Shooting Drill gives +1 SHO). The boost must be modest and must respect the existing OVR/potential caps—if a player is already maxed in that attribute or OVR would exceed potential, the stat increase should be blocked (with an appropriate message), but XP can still be awarded."

## Current System Snapshot *(baseline — what exists today)*

Managers run **Stat Training Drills** from `/development` → **Training Drills**. There are **six** skill drills, each mapped to **exactly one** attribute:

| Drill | Attribute |
|-------|-----------|
| Pace Sprint | PAC |
| Finishing Drill | SHO |
| Distribution Drill | PAS |
| Dribbling Drill | DRI |
| Tackling Drill | DEF |
| Strength Drill | PHY |

**Today’s rewards (post US-23):** drills grant **XP only**. Costs (action energy + coins), club daily limit (**20**), and per-card daily limit (**5**) still apply. The post-drill summary explicitly tells managers that OVR is unchanged and that they should spend skill points to raise stats. There are **no** multi-attribute drills in the live catalog.

**Historical note:** Older drill behavior granted a direct `+1` attribute and was deliberately replaced by XP + skill allocation for progression pacing. This feature **intentionally amends** that XP-only rule by restoring a **modest** focused attribute bump **alongside** XP—not by removing skill allocation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Feel a focused training payoff (Priority: P1)

A manager opens Training Drills, picks a player and a skill drill (e.g. Finishing), and runs it. When the player still has room under attribute and potential caps, the summary shows both XP gained **and** `+1` to the trained attribute (and any resulting OVR change).

**Why this priority**: The complaint is that drills feel unrewarding; tangible attribute feedback is the core product change.

**Independent Test**: Run one uncapped Finishing Drill on an eligible player and confirm the summary reports XP plus `+1 SHO` (and updated OVR if the rating formula changes).

**Acceptance Scenarios**:

1. **Given** a non-retired eligible player whose SHO can rise by 1 without exceeding the individual attribute ceiling or the player’s potential overall ceiling, **When** the manager runs Finishing Drill, **Then** the player receives the normal drill XP **and** SHO increases by exactly 1.
2. **Given** that successful drill, **When** the post-drill summary is shown, **Then** it clearly names the attribute gained (e.g. `+1 SHO`) and does not claim OVR is unchanged if OVR actually changed.
3. **Given** any of the six drills, **When** run under the same uncapped conditions, **Then** only the mapped attribute for that drill increases by 1 (no other attributes change from the drill boost).

---

### User Story 2 - Cap blocks attribute, not the whole drill (Priority: P1)

When the targeted attribute cannot rise (already at the attribute ceiling, or `+1` would push overall above potential), the drill still completes: energy/coins/daily slots are consumed as today, XP is still awarded, and the manager sees a clear message that the attribute boost was blocked and why.

**Why this priority**: Managers must not feel cheated on XP when a card is near pot, and they must understand why the attribute did not move.

**Independent Test**: Force each block reason on a scripted card, run the matching drill, and verify XP success + blocked-stat messaging with no attribute change.

**Acceptance Scenarios**:

1. **Given** a player whose targeted attribute is already at the individual attribute ceiling, **When** the matching drill runs, **Then** XP is awarded, the attribute does not increase, and the summary explains the attribute is maxed.
2. **Given** a player for whom `+1` to the targeted attribute would cause overall to exceed potential, **When** the matching drill runs, **Then** XP is awarded, the attribute does not increase, and the summary explains potential/overall would be exceeded.
3. **Given** either blocked case, **When** the drill completes, **Then** energy, coins, and daily drill counters are still consumed exactly as for a normal successful drill (the attempt is not free and not rolled back).

---

### User Story 3 - Preview and summary honesty (Priority: P2)

Before running a drill, the drill picker helps the manager expect attribute gain (or that it may be blocked). After running, the summary always distinguishes “XP + attribute” vs “XP only (attribute blocked)”.

**Why this priority**: Trust in the Training Drills surface depends on matching expectation to outcome; secondary to actually granting the boost.

**Independent Test**: Open the drill picker for an uncapped and a capped player; run both; confirm preview language and post-run summary stay consistent with the outcome.

**Acceptance Scenarios**:

1. **Given** an uncapped selected player, **When** viewing drill options, **Then** each option indicates the targeted attribute gain (e.g. `+1 SHO`) in addition to XP/energy preview.
2. **Given** a player who cannot receive the attribute boost for the selected drill, **When** viewing options or after running, **Then** copy does not promise a guaranteed attribute increase that will not happen (blocked outcome is explicit).
3. **Given** a successful attribute boost, **When** the hub refreshes after the run, **Then** the player’s shown ratings reflect the new attribute/OVR without requiring a separate command.

---

### Edge Cases

- Player at potential overall already: attribute boost blocked; XP still granted.
- Targeted attribute at individual ceiling (99) while overall is still under potential: that drill’s attribute boost is blocked; other attributes’ drills may still boost if uncapped.
- Double-tap / concurrent Run Drill: existing match-lock and atomic drill rules still prevent double rewards; at most one boost per successful completion.
- Card in hospital / injured / active evolution / transfer list / match lock: existing blocks remain; this feature does not reopen those paths.
- Club at 20/20 or card at 5/5 daily drills: existing limit errors remain; no attribute change without a completed drill.
- Bot-controlled clubs: same drill rules if they use the same training path; no special bypass.
- Stale Training Drills embed after bot restart: manager re-opens from `/development`; out of scope to revive expired ephemeral views.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Completing a Stat Training Drill MUST continue to award drill XP under the existing XP rules (diminishing returns, age multiplier, training-ground bonus, and existing energy/coin costs).
- **FR-002**: Completing a Stat Training Drill MUST attempt to grant **exactly +1** to the single attribute mapped to that drill (PAC, SHO, PAS, DRI, DEF, or PHY).
- **FR-003**: The attribute boost MUST be evaluated **before** it is applied. If the targeted attribute is already at the individual attribute ceiling, or applying `+1` would cause overall to exceed the card’s potential, the boost MUST NOT be applied.
- **FR-004**: When the attribute boost is blocked by FR-003, the drill MUST still complete successfully for XP and cost/limit accounting, and the manager MUST receive a clear reason that the attribute did not increase.
- **FR-005**: When the attribute boost is applied, overall MUST be recalculated with the same rating rules used elsewhere so displayed OVR stays consistent with the new attributes.
- **FR-006**: Drill selection and post-drill summary UI MUST surface attribute outcomes clearly: promised/targeted `+1` when available, and explicit “attribute blocked” messaging when not.
- **FR-007**: Existing Training Drills eligibility, costs, club daily limit (20), per-card daily limit (5), match lock, evolution lock, transfer-list lock, injury/hospital blocks, and ownership checks MUST remain enforced.
- **FR-008**: Skill allocation MUST remain available as the flexible path for spending skill points; the drill boost does **not** consume skill points.
- **FR-009**: No new slash command, hub button, or drill type is required for this change; behavior extends the existing six single-attribute drills.
- **FR-010**: Existing player cards and historical drill history MUST remain valid without a data backfill (behavior change is forward-looking only).

### Key Entities

- **Stat Training Drill**: Instant training action on one card that costs energy/coins, consumes daily drill capacity, grants XP, and may grant a focused attribute boost.
- **Target Attribute**: The single PAC/SHO/PAS/DRI/DEF/PHY field mapped to the chosen drill.
- **Attribute Ceiling**: Hard per-stat maximum (currently 99) that blocks further boosts to that attribute.
- **Potential Ceiling**: Card potential overall; a boost that would push computed overall above potential is blocked.
- **Drill Outcome Summary**: Player-facing result showing XP, whether `+1` applied or was blocked (with reason), costs spent, and updated ratings when changed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of QA cases where a card can legally take `+1` in the trained attribute, a completed drill grants both XP and that `+1` on the first successful run.
- **SC-002**: In 100% of QA cases at attribute ceiling or where `+1` would exceed potential, the completed drill grants XP, leaves the attribute unchanged, and shows a block reason the tester can match to the rule.
- **SC-003**: Managers can tell from the post-drill summary alone whether the attribute rose—no need to open a separate profile solely to discover the outcome (spot-check: 10/10 scripted runs).
- **SC-004**: Under full daily use, a single card cannot gain more than **5** drill attribute points per UTC day (one per completed card drill), preserving the existing per-card drill cap as the pacing bound.
- **SC-005**: Club-wide completed drills remain capped at **20** per UTC day; this feature does not raise drill throughput.
- **SC-006**: Player-facing complaints that “drills only give XP / feel useless” should drop for this specific complaint after launch (qualitative: support can point to visible `+1` on uncapped runs).

## Assumptions

- Each live drill continues to target **exactly one** attribute; there are no multi-stat drills today. If a multi-stat drill is added later, that design chooses separately between `+1` to each vs player choice—out of scope here.
- Attribute boost amount is always **+1** for both basic and advanced energy/XP tiers (tier affects cost/XP only, not boost size).
- Cap evaluation uses the same ceilings managers already know from skill allocation / evolution: per-stat max **99** and overall must not exceed **potential**.
- Blocked-boost drills still charge energy, coins, and daily counters—managers are paying for training that yields XP even when the attribute is capped.
- The drill `+1` does not spend skill points and does not replace Allocate Skills; it is a modest focused bonus on top of XP.
- This feature deliberately amends the prior “drills grant XP only” progression rule; SDD / agent guidance that still says XP-only must be updated when the change ships.
- No schema migration is required for existing cards; any persistence change is limited to forward reward behavior on the existing drill action.
- Recover, fusion, evolutions, and mentor transfusion are unchanged.
