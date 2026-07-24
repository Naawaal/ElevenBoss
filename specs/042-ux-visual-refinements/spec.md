# Feature Specification: Store / Swap / Hospital UX Refinements

**Feature Branch**: `042-ux-visual-refinements`

**Created**: 2026-07-23

**Status**: Draft

**Input**: User description: "Three targeted UX refinements: (1) disable Buy Energy Refill when energy is at or near maximum with clear near-full feedback; (2) visual player comparison on the squad swap screen; (3) Hospital panel uses the prepared hospital image asset with dynamic patient representation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Near-Full Energy Refill Guard (Priority: P1)

A manager opens the Club Store with action energy already at or near the club’s maximum. They see the Buy Energy Refill control greyed out and unusable, with clear copy that energy is already full or near the cap. They are not charged and do not need to discover the limit by attempting a purchase. When energy later drops below the near-full threshold (after spending energy), the control becomes available again with normal purchase labeling.

**Why this priority**: Prevents wasted coins and confusing failed purchases; smallest, highest-clarity UX win with immediate player trust impact.

**Independent Test**: Open Store with energy at/near max and confirm the refill control is disabled with near-full messaging; open Store with energy clearly below the threshold and confirm the control is enabled and purchase still works as today.

**Acceptance Scenarios**:

1. **Given** the club’s current action energy is at or above the near-full threshold relative to max energy, **When** the manager opens `/store`, **Then** Buy Energy Refill is visibly disabled (greyed out) and cannot be activated, and the store shows a clear near-full reason (e.g. “Energy already full” or “Near maximum”).
2. **Given** current energy is below the near-full threshold, **When** the manager opens `/store`, **Then** Buy Energy Refill is enabled with normal purchase labeling and behaves as today (cost tiers, +energy, balance refresh).
3. **Given** the manager’s energy was near full (button disabled) and then drops below the threshold without leaving the session, **When** the store view is refreshed after an energy-consuming action or a store reopen, **Then** Buy Energy Refill is enabled again.
4. **Given** energy is near full, **When** the manager interacts with other store actions (daily login, gacha, facilities), **Then** those actions remain available and are unaffected by the refill guard.

---

### User Story 2 - Visual Squad Swap Comparison (Priority: P2)

A manager opens Swap Players from the squad hub. Instead of (or in addition to) text-only selection, they see a visual comparison of the players involved in the swap—at minimum a clear side-by-side representation of the currently selected starter and reserve (names, position, overall, and key attributes visible enough to decide). Dropdown/selection controls may remain for choosing who to swap. Confirm stays gated until both sides are selected and eligible.

**Why this priority**: Swap mistakes are costly to squad strength; visual comparison reduces cognitive load versus scanning long text lists alone.

**Independent Test**: Open Swap with a valid XI and at least one healthy compatible reserve; select both sides and confirm a visual comparison appears before Confirm; confirm swap still applies correctly.

**Acceptance Scenarios**:

1. **Given** the manager has a starting XI and at least one healthy reserve eligible for some slot, **When** they open Swap Players, **Then** the swap screen shows a visual comparison area (side-by-side player cards or an equivalent highlighted pitch/slot graphic) plus the existing selection flow.
2. **Given** the manager selects a starter and a compatible reserve, **When** the selection updates, **Then** the visual comparison updates to those two players so attributes can be compared before Confirm.
3. **Given** both selections are ready and eligible, **When** the manager confirms, **Then** the swap completes as today and the hub reflects the new lineup.
4. **Given** the manager has not finished selecting both sides, **When** they view the swap screen, **Then** Confirm remains unavailable and the visual area shows empty/placeholder state for any unselected side without implying a completed swap.

---

### User Story 3 - Visual Hospital Patient Panel (Priority: P3)

A manager opens the Hospital / Medical Center panel. Admitted patients are shown using the project’s prepared hospital image asset (themed hospital / bed scene), not only a plain text list. Patient identity (at least name) is associated with the visual so the manager can see who occupies beds. When players are admitted or discharged, reopening or refreshing the hospital panel shows an updated visual that matches current occupancy. Empty hospital and waiting-list cases remain understandable.

**Why this priority**: Hospital is already a high-stakes facility surface; visual occupancy makes bed usage and recovery status easier to scan, especially on mobile Discord.

**Independent Test**: Open Hospital with zero patients (empty visual + clear empty copy); admit one or more patients and reopen (visual shows them); discharge until empty and confirm visual returns to empty state while waiting/injured-out copy still works.

**Acceptance Scenarios**:

1. **Given** one or more players are currently admitted, **When** the manager opens the Hospital panel, **Then** they see the prepared hospital visual with admitted patients represented (names overlaid or otherwise clearly associated with bed/patient slots), and recovery-relevant text (severity/ETA) remains available either on the image or in accompanying panel text.
2. **Given** no players are admitted, **When** the manager opens the Hospital panel, **Then** they see the hospital visual in an empty-beds state (or equivalent) plus clear copy that nobody is admitted—not a broken/missing image.
3. **Given** patients are admitted or discharged between views, **When** the manager refreshes/reopens Hospital, **Then** the visual matches the current admitted set (no stale names from a previous visit).
4. **Given** injured players are waiting with no free bed, **When** the manager opens Hospital, **Then** waiting players remain listed/indicated (visual may focus on admitted beds; waiting must not disappear silently).

---

### Edge Cases

- **Energy exactly at max**: Treat as near-full; refill control disabled with “Energy already full” (or equivalent).
- **Energy within threshold but not max** (e.g. max 120, current 116 with a “within 5” rule): Disable with “Near maximum” (or equivalent); do not charge.
- **Energy max or threshold data missing / unavailable**: Fail safe—keep refill enabled and rely on existing purchase error messaging rather than falsely locking the button forever.
- **Swap with zero reserves / empty bench**: Swap screen still opens; reserve selection and Confirm stay unavailable; visual shows no “in” player; clear empty-bench messaging.
- **Swap with reserves but none compatible with selected starter’s slot**: Visual does not show an invalid pair; Confirm stays off; message explains no compatible reserve.
- **Swap with injured-only reserves**: Injured reserves are not selectable; same empty/ineligible treatment as today.
- **Hospital at max bed capacity**: Visual shows all occupied beds; upgrade/admit flows unchanged by this feature.
- **Hospital image asset missing at runtime**: Fall back to the current text patient list so Hospital remains usable.
- **Many admitted patients vs bed slots on the asset**: Cap visual slots to the asset’s designed bed count; overflow patients remain in accompanying text so nobody is hidden.
- **Stale ephemeral store/swap/hospital message after energy or roster changes elsewhere**: On next open/refresh of that surface, state and visuals are recomputed from current club data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Club Store MUST disable Buy Energy Refill when current action energy is at or above the near-full threshold relative to the club’s maximum action energy.
- **FR-002**: The near-full threshold MUST be: current energy ≥ 95% of max **or** current energy within 5 points of max (inclusive), whichever condition is met first. Disabled label/copy MUST distinguish full (`Energy already full`) vs near-full (`Near maximum`) when practical; if only one label fits the control, prefer the more accurate of the two for the current value.
- **FR-003**: When disabled for near-full reasons, Buy Energy Refill MUST be visually greyed out / non-interactive and MUST NOT deduct coins or grant energy.
- **FR-004**: When energy is below the near-full threshold, Buy Energy Refill MUST remain available and MUST preserve existing refill pricing, daily tier costs, and success/error outcomes.
- **FR-005**: The Store MUST recompute refill availability from current energy whenever the store hub is shown or refreshed after a successful store action.
- **FR-006**: The Squad Swap screen MUST present a visual comparison of the swap participants (side-by-side player cards **or** pitch/slot highlight showing the two involved players). Text selection controls MAY remain as the primary chooser.
- **FR-007**: The swap visual MUST update when the selected starter and/or reserve changes, and MUST show a clear placeholder for any side not yet selected.
- **FR-008**: Swap eligibility rules (healthy reserves, formation-slot compatibility, Confirm gating) MUST remain unchanged; visuals MUST NOT allow confirming an invalid pair.
- **FR-009**: When there are zero eligible reserves (empty bench, all injured, or none compatible), the swap UI MUST remain usable for browsing/backing out, with Confirm disabled and messaging that no valid swap partner is available.
- **FR-010**: The Hospital panel MUST display the prepared hospital image asset from the project assets library as the primary visual for admitted patients.
- **FR-011**: The hospital visual MUST reflect the current admitted patient set (names at minimum) and MUST update on admit/discharge when the panel is next shown or refreshed.
- **FR-012**: An empty hospital MUST show an empty-state visual (or empty beds on the asset) plus explicit “no one admitted” messaging.
- **FR-013**: Waiting (no bed) injured players MUST still be discoverable in the Hospital panel even when the visual focuses on admitted beds.
- **FR-014**: If the hospital asset cannot be loaded, the panel MUST fall back to the existing text patient list without blocking Hospital management actions (admit/discharge/upgrade as already available).
- **FR-015**: These refinements MUST NOT introduce new slash commands, new economy pipes, or changes to refill amounts/pricing, swap RPC semantics, or hospital recovery math.

### Key Entities

- **Action Energy Balance**: Club current energy and max energy used to decide Store refill availability and near-full messaging.
- **Swap Pair**: The currently selected starter (out) and reserve (in), plus eligibility flags used for Confirm and for driving the comparison visual.
- **Hospital Occupancy**: Admitted patient cards (name, injury severity, expected return) mapped onto visual bed/patient slots; waiting list separate from admitted occupancy.
- **Hospital Visual Asset**: Prepared themed hospital/bed image used as the base for the Hospital panel presentation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of Store opens where energy meets the near-full rule, Buy Energy Refill is disabled before any purchase attempt, with near-full/full reason visible without opening a separate help screen.
- **SC-002**: Managers with energy below the threshold can still complete a refill purchase in the same number of taps as today (no extra confirmation steps added by this feature).
- **SC-003**: On the Swap screen, after selecting both players, managers can identify both participants’ names, positions, and overall ratings from the visual comparison in under 5 seconds without reading only the dropdown option text.
- **SC-004**: At least 90% of swap confirmation attempts in usability checks are made only after both sides are visibly selected (Confirm remains gated for incomplete pairs).
- **SC-005**: Opening Hospital with N admitted patients (N ≥ 1) shows all admitted names associated with the hospital visual or accompanying panel text within one view; empty hospital never shows leftover names from a prior occupancy.
- **SC-006**: Admit or discharge followed by reopening Hospital updates the visual/text occupancy to match server state on that open—no stale patient names remain.
- **SC-007**: Zero regressions in refill purchase success when energy is low, swap success when both sides are eligible, and hospital admit/discharge/upgrade outcomes versus pre-feature behavior.

## Assumptions

- Near-full uses the combined rule in FR-002 (95% **or** within 5 of max); refill grant size (+50) is unchanged, so near-full disables purchases that would mostly waste capacity even if the economy layer would otherwise allow a buy.
- Discord controls may express “tooltip” intent via disabled button label and/or adjacent embed field text when native tooltips are unavailable.
- Swap visual **augments** the existing dual-select flow rather than replacing it in v1 (selection remains text/select-based; comparison is visual).
- Default swap visual style is **side-by-side comparison cards** for the selected pair; a pitch highlight is an acceptable alternative if it better reuses existing pitch visuals, as long as FR-006–FR-009 are met.
- The prepared hospital asset already in the project assets folder (hospital/admitted themed image) is the base art; dynamic content is limited to overlaying current patient identity (and optional severity/ETA) onto that base, not redesigning hospital math.
- Overflow beyond visually available bed slots is handled in text (FR edge case); bed capacity rules stay owned by existing facility logic.
- No schema/RPC changes are required for these UX-only refinements; if a future plan discovers a hard dependency, that is out of scope for this feature’s functional intent and must be called out in planning.
- Out of scope: changing energy refill price tiers, changing max energy, redesigning the full squad hub, new hospital upgrade UI, or new slash commands.
