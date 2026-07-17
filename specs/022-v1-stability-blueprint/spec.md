# Feature Specification: v1 Stability Blueprint

**Feature Branch**: `022-v1-stability-blueprint`

**Created**: 2026-07-15

**Status**: Implemented (Wave 0–3 core + polish; Medium Suspects + M6/L2 timebox backlog)

**Input**: User description: "Systematically identify, prioritize, and fix all outstanding bugs, loopholes, and other issues before moving forward — master bug-fixing blueprint to stabilize the bot for v1.0.0. Collect known issues (SelectMenu disappearance, OVR inconsistencies, resource race conditions, stale match data, retroactive reward edges, plus recent-feature loopholes), categorize by severity/module, propose fix plans with dependencies, prioritize sequence by risk/impact/effort, and identify new edge cases from mentor, hospital, transfer market, and league automation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Freeze a trusted defect registry (Priority: P1)

As the product owner, I can see one authoritative inventory of every known defect and suspected loophole for v1.0.0 — each with severity, module, status (open / verified-fixed / intentional), and expected correct behavior — so we stop rediscovering the same bugs across chats.

**Why this priority**: Without a single list, Critical money/integrity bugs and Low polish issues get mixed, and “already fixed” audit items get re-investigated forever.

**Independent Test**: Review the catalog below; every item has ID, severity, module, symptom, expected behavior, and remediation intent; zero unnamed “that Discord bug” handwaves.

**Acceptance Scenarios**:

1. **Given** prior audits (US-23/24/25/29), AGENTS regression notes, and feature research debt (005–021), **When** the registry is published, **Then** each named concern in the Input is present with an ID.
2. **Given** an issue that was already remediated in production (e.g. bot economy pipe), **When** listed, **Then** it is marked **Verify** (regression check), not as if still unbroken, unless a live repro exists.
3. **Given** intentional design (friendly sandbox, weekly ladder vs season standings), **When** listed, **Then** it is labeled **Intentional** so it is not “fixed” into a new feature.

---

### User Story 2 — Close Critical integrity & money risks first (Priority: P1)

As a manager, I never lose coins, gain duplicate cards, or receive progress from a double-submit or race; as a peer manager, my sales and league results are likewise atomic and once-only.

**Why this priority**: Economy and ownership corruption destroys trust faster than any UX polish can repair.

**Independent Test**: Scripted double-invoke / concurrent-buy / payroll-retry / MoMD-resettle cases show at most one success and ledger consistency; losers get a clear message.

**Acceptance Scenarios**:

1. **Given** two managers confirm the same transfer listing at once, **When** both complete, **Then** exactly one purchase succeeds and neither side has partial coin/card state.
2. **Given** weekly payroll or MoMD settlement retries, **When** jobs re-run, **Then** coins move at most once (idempotent run keys).
3. **Given** a manager double-taps Mentor Transfusion, drill, pack claim, or hub Buy, **When** Discord delivers two interactions, **Then** daily caps and ledger keys prevent double grant.

---

### User Story 3 — Stop UI disappearing / stale hub pain (Priority: P2)

As a manager on mobile, when I use hospital, academy, marketplace, development, or squad selects, the Select menus and buttons I need remain usable after an action or do not silently vanish without guidance to re-open the hub.

**Why this priority**: High visibility; players interpret empty Select rows as “the bot broke” even when backend state is correct.

**Independent Test**: Scripted hub flows that empty/refill option lists (last patient discharged, last listing sold, filter with zero results) leave a clear empty-state message and a recoverable path (re-run command / Back), never a blank interactive shell.

**Acceptance Scenarios**:

1. **Given** a hub Select becomes empty after an action, **When** the message is refreshed, **Then** the manager sees explicit empty-state copy and a Back / re-open affordance — not a missing control with no explanation.
2. **Given** a hub view times out after the allowed window, **When** the manager presses a stale control, **Then** they get a clear “session expired — run the command again” style outcome.
3. **Given** filter/browse selects on Transfer Board with zero matches, **When** results render, **Then** empty-state copy appears and filter controls remain or a Change Filters path stays available.

---

### User Story 4 — Make OVR / card truth consistent (Priority: P2)

As a manager, the overall I see on pack open, profile, marketplace browse, and match power never “looks like a 75, plays like a 72” for new cards; legacy inflated cards are either corrected or clearly inventoried as residual drift.

**Why this priority**: Progression and transfer pricing trust depends on True OVR and stored `overall` staying coherent.

**Independent Test**: New factory/pack cards assert printed OVR equals True OVR; allocate/mentor/evo claim paths cannot push displayed overall past potential rules; Ops has a defined stance on leftover inflated legacy rows.

**Acceptance Scenarios**:

1. **Given** a newly generated card, **When** displayed anywhere, **Then** shown OVR equals True OVR under the published formula.
2. **Given** skill allocation or evolution claim, **When** stats change, **Then** stored overall remains consistent with True OVR / POT clamps (no silent overshoot).
3. **Given** historical cards with known inflation, **When** the stability wave completes, **Then** either they are batch-corrected under an approved fair rule or explicitly deferred with a count — not left as “maybe later” without decision.

---

### User Story 5 — Match & progression parity without regressions (Priority: P2)

As a manager, bot and league matches still grant correct XP/coins/fatigue through the single pipes; friendly stays a sandbox; evolution progress does not double-tick; squad/match gates (injury, contract grace, squad invalid, strikes) agree across UI and enforcement.

**Why this priority**: Past half-wired match paths (US-29) and friendly double-evolution were real shipping bugs; recent wage/league flags multiply gate surfaces.

**Independent Test**: Regression checklist for match types + evolution tick count + validity gates passes; no flat hardcoded XP remaining on live paths.

**Acceptance Scenarios**:

1. **Given** bot vs league vs friendly match conclusion, **When** rewards run, **Then** each type matches the published economy/XP contract (friendly: log only).
2. **Given** one match that already ticks evolution inside match-result processing, **When** the match flow ends, **Then** evolution progress advances exactly once for those cards.
3. **Given** past-grace XI or strike≥2/≥3, **When** starting friendly / listing / scouting / matching, **Then** blocks match documented ladder with named reason copy.

---

### User Story 6 — Harden recent-feature edges before enablement (Priority: P2)

As ops enabling transfer market, wages, League Dynamics, or automation on a pilot guild, flag-on reveals no obvious loopholes (tax evasion, free wage skip, double season start, MoMD farm via auto-sim, listed XI still playing).

**Why this priority**: Feature flags are still off by default; enabling without a stability pass risks mass ticket noise.

**Independent Test**: Pilot checklist per flaged feature (017–021) + mentor/hospital edges runs green before production default-on considerations.

**Acceptance Scenarios**:

1. **Given** automation on, **When** registration closes and Start is hidden, **Then** no duplicate seasons / double daily sims occur.
2. **Given** wages on and coins insufficient, **When** Monday payroll runs, **Then** debt/strikes update atomically and Finances shows the truth.
3. **Given** a card is transfer-listed, evo-active, hospitalized, or past-grace, **When** conflicting actions are attempted, **Then** RPC and UI agree on the block.

---

### User Story 7 — Ship a prioritized remediation sequence (Priority: P3)

As the engineering owner, I execute fixes in risk order (Critical → High → Medium → Low), bundling dependent items, and stop when the measurable v1.0.0 stability bar is met — not when every Low polish idea is done.

**Why this priority**: Sequencing is the blueprint’s delivery mechanism; without it, Critical and Low compete for the same slots.

**Independent Test**: The Fix Sequence section orders Waves 0–4; each Wave has an exit gate; Low polish is explicitly optional after the bar.

**Acceptance Scenarios**:

1. **Given** Wave 0 (verify already-shipped audit fixes), **When** complete, **Then** known-fixed items are reclassified or reopened with repro.
2. **Given** Waves 1–2 complete, **When** measured against Success Criteria, **Then** Critical/High economic and integrity issues are closed.
3. **Given** residual Low items, **When** timebox ends, **Then** they remain tracked as backlog, not silent blockers to v1.0.0 declare.

---

### Edge Cases

- Bot restart mid-hub: persistent vs ephemeral views behave differently; managers may still click stale custom_ids.
- Flag transitions mid-season (automation/dynamics/wages): in-flight seasons vs next season rules must not double-apply rewards.
- Transfer sell after buyer already loading stale price: expected-price guard must reject.
- Mentor at exact daily cap or exact XP headroom: no overflow SP burn without youth XP grant.
- Hospital discharge of last patient empties Select options — Discord requires ≥1 option; view rebuild must not crash or leave a ghost disabled strip unexplained.
- League auto-sim then manual play attempt: fixture already resolved; no second result.
- All-auto-sim matchday: MoMD must not award.
- AI/`is_ai` clubs: payroll exempt; must not create human debt via bot fill.
- Card owner changes (P2P) with pending level rewards: claim follows current owner, not frozen historical club.
- Schema guard / migration numbering mistakes: deploy must fail closed, not ship half-applied RPCs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST maintain a living **Issue Registry** (this spec’s catalog + status updates during remediation) covering severity (Critical / High / Medium / Low), module, symptom, expected behavior, dependencies/bundles, and status.
- **FR-002**: Remediation MUST prioritize by severity first, then user impact, then effort — Critical money/ownership/integrity before Medium/Low polish.
- **FR-003**: Every Critical/High fix MUST leave behind a small automated check or documented smoke path that fails if the bug returns.
- **FR-004**: Resource mutations that move coins, card ownership, evolution progress, mentor transfers, payroll, or MoMD awards MUST remain single-pipe / idempotent under double-invoke and concurrent races.
- **FR-005**: Discord hubs that use Select menus MUST handle empty option sets without unexplained control disappearance (empty-state copy + recovery path).
- **FR-006**: New card creation MUST keep displayed overall equal to True OVR; progression mutations MUST keep overall/POT rules coherent; legacy OVR inflation disposition MUST be decided and recorded (fix batch vs deferred with counts).
- **FR-007**: Match-type reward contracts (bot / league / friendly) and evolution tick-once rules MUST be regression-verified as part of Wave 0–1.
- **FR-008**: Recent feature surfaces (Mentor, Hospital, Transfer Market, Wages, League Dynamics, League Automation) MUST have an edge-case pass before recommending flag enablement beyond pilots.
- **FR-009**: Intentional non-bugs (friendly sandbox, dual ladders/copy distinction, flag-off forecast wages) MUST remain labeled Intentional and MUST NOT be “fixed” into scope creep.
- **FR-010**: Scope of this feature is **stabilize / fix / verify** — not new gameplay systems. New product features require their own specs.
- **FR-011**: Player-facing regressions discovered and fixed during this wave MUST update `change_log.md` when they affect manager-visible behavior.
- **FR-012**: SDD source of truth (`.specify/specs/v1.0.0/` and this feature folder) MUST be updated when remediation reveals behavioral contract changes.

### Issue Registry (seed inventory)

Status key: **Open** = needs work; **Verify** = believed fixed — confirm with regression; **Intentional** = not a defect; **Suspect** = plausible loophole from recent features, needs prove/disprove.

#### Critical

| ID | Module | Issue | Status | Remediation intent | Bundle |
|----|--------|-------|--------|--------------------|--------|
| C1 | Economy / Transfer | Concurrent P2P purchase could double-debit or duplicate ownership if locking regresses | Closed | Wave 0: `tests/test_transfer_market_race.py` green (2026-07-15) | B-Transfer |
| C2 | Economy / Wages | Weekly payroll retry double-bills clubs | Closed | Wave 0: wage math tests green; unique week_key path unchanged | B-Wages |
| C3 | League / MoMD | Manager of the Matchday double-pay on resettle / tick retry | Closed | Wave 0: `tests/test_momd_selection.py` green | B-League-Tick |
| C4 | League / Automation | Automation + Dynamics jobs double-sim fixtures or start duplicate seasons | Closed | Wave 0: single `league_state_machine_job` @ 00:05; interval auto-sim skips non-legacy | B-Automation |
| C5 | Economy / Progression | Any remaining coin/XP mutation outside the approved single pipes | Closed | Wave 0: no direct coins UPDATE / flat XP 15 in apps | B-Audit |

#### High

| ID | Module | Issue | Status | Remediation intent | Bundle |
|----|--------|-------|--------|--------------------|--------|
| H1 | UI/UX | SelectMenu “disappearance” after admit/discharge, list empty, filter zero, or hub rebuild | Closed | `add_select_if_options` + empty copy; hospital/academy/marketplace wired; `tests/test_select_empty_state.py` | B-UI-Select |
| H2 | Match / Progression | Friendly evolution double-tick (historical) or any second tick outside `process_match_result` | Closed | Wave 0: zero Python `tick_evolution_match_progress` callers; friendly = logs only | B-Match-Parity |
| H3 | Player / OVR | Stored `overall` vs True OVR drift (mentor/allocate trust stored; legacy inflated cards) | Closed (deferred legacy) | Factory ≥200 creates assert overall==True OVR (`test_player_factory_ovr.py`). Legacy inflation dry-run **deferred** — no DATABASE_URL in implement session; ops should run `scripts/fix_inflated_player_stats.py` before wider enablement | B-OVR |
| H4 | Economy / Transfer | Stale browse/price UI lets buyer confirm outdated listing state | Closed | Wave 0: purchase expected-price + race tests still green | B-Transfer |
| H5 | Progression | Retro claim after ownership change / DM-blocked notify edge cases | Closed | Wave 0: claim RPC uses `p_owner_id`; notifier groups by `owner_id` | B-Retro |
| H6 | Match Engine / UX | Stale prematch/squad snapshot used after lineup change mid-flow | Disproven | Formation mid-match blocked; no Wave 0 repro — leave backlog if field reports appear | B-Match-Stale |
| H7 | Database | Deploy/schema guards miss required tables or procedures and ship half-broken seasons | Closed (deferred smoke) | Wave 0: no schema verify run (no DATABASE_URL); scripts present; mark ready when ops verifies remote | B-Schema |
| H8 | Training / Evolution | Evolution hub copy/config/cost/slot drift vs real rules (`018` known debt) | Closed | Removed PlayStyle hub lie; cooldown package mirror → 6h matching `game_config` seed; slots stay 3 | B-Evo-Truth |
| H9 | Economy / Transfer | Listed card still playable / in XI (data race) | Closed | Wave 0: peer guards + race suite green | B-Transfer |

#### Medium

| ID | Module | Issue | Status | Remediation intent | Bundle |
|----|--------|-------|--------|--------------------|--------|
| M1 | Mentor | Double-submit / stale Allocate embed / exact headroom races | Disproven (unit) | Daily log + headroom raise in RPC; UI disable is sugar | B-Mentor |
| M2 | Hospital / Fatigue | UI gates disagree with enforcement (admit, recovery, injury play-on) | Disproven | Profile/store share `show_hospital_panel`; injury empty → play_on path | B-Hospital |
| M3 | Wages / Squad | Contract grace warnings vs past-grace assign/match blocks incomplete on a path | Disproven | `squad_validity` + `human_club_xi_ok` in battle match gates | B-Wages |
| M4 | League | Hub deadline / announce digest missing when automation flag on | Suspect | Needs automation-on pilot | B-Automation |
| M5 | Marketplace | Expired listings linger on the board until the next clean-up pass | Open (accepted short-term) | Keep expiry job reliable; later may move expiry into browse rules | B-Transfer |
| M6 | Profile / Copy | Dual ladders (bot Division Rank vs season Pts) still confuse managers | Closed | Profile + league standings footer clarify three ladders | B-Copy |
| M7 | Admin | Temporary admin “run cycle now” controls still present after cron is trusted | Open | Remove once midnight automation is trusted in production | B-Automation |
| M8 | Render / Ops | Login/Cloudflare retry / health server quirks cause flaky uptime perception | Intentional ceiling | Document ceiling; not a gameplay defect | — |

#### Low

| ID | Module | Issue | Status | Remediation intent | Bundle |
|----|--------|-------|--------|--------------------|--------|
| L1 | Dead code | Leftover debug paths / no-op regen job (US-29 H8/H10) | Closed | Removed `debug_session_log.py` + `match_xp` agent logs (2026-07-15) | B-Hygiene |
| L2 | Tests | Broken/outdated imports in legacy test modules | Closed | Full suite green (281+); injury ETA tests aligned to 016; squad swap fake hub fixed | B-Hygiene |
| L3 | Economy sim | Agent-sale day budget estimates are approximate | Intentional | Leave until economy redesign; document | — |
| L4 | Formation | Wingback band confusion (3-5-2 MID vs 5-3-2 DEF) | Closed | `tests/test_audit_fixes.py` green | B-Match-Parity |
| L5 | UX | Seller DM on successful P2P sale (out of scope v1 transfer) | Intentional | Do not add in stability wave | — |

#### Recent-feature edge cases (must prove/disprove)

| ID | Feature | Suspected loophole | Verdict (2026-07-15) | Severity if true |
|----|---------|-------------------|----------------------|------------------|
| E1 | Mentor | Transfer SP near POT ceiling without matching youth XP grant | Disproven — `preview_mentor_transfer` / headroom math blocks overshot units | High |
| E2 | Mentor | Transfer while evo-locked / transfer-listed / hospitalized | Disproven as money loophole — RPC allows (card still owned); optional UI soft-lock out of scope | Medium |
| E3 | Hospital | Discharge + re-admit loops to skip fatigue drain timing | Disproven — discharge keeps injury clock; admit recalculates recovery days; no fatigue faucet | Medium |
| E4 | Transfer | List → cancel → re-list to dodge tax/cooldown edges | Disproven for free flip — `transfer_relist_cooldown_hours` enforced on create | Medium |
| E5 | Transfer | Buyer senior roster overflow after youth promote race | Disproven — purchase locks buyer + senior count `FOR UPDATE` vs `senior_roster_cap` | High |
| E6 | Wages | Shrink XI after payroll snapshot timing within the Monday job window | Disproven — club row `FOR UPDATE` then bill derived under lock | Medium |
| E7 | Wages | Strike≥3 blocks market but not agent-sale — confirm intentional, document | Intentional — market/scout guarded; agent sale allowed by design | Low |
| E8 | Dynamics | Hub opportunistic auto-sim races midnight tick on dynamics seasons | Disproven as harmful double-pay — hub opportunistic sim intentional (020); interval skips dynamics; `is_played` gates re-resolve | High |
| E9 | Automation | Pause mid-registration leaves orphan registration season | Disproven for duplicates — `can_open` blocks while active/reg/paused exists | Medium |
| E10 | Automation | Force End then auto-registration reopens same day contrary to Monday rule | Closed (fixed) — Force End under automation sets `next_auto_registration_at` to next Monday 00:05 | Medium |
| E11 | Evolutions | Cancel cooldown used to farm soft-lock evasion while still ticking matches | Intentional — cancel fee unlocks soft-lock; cooldown still gates next start | Medium |
| E12 | Level rewards | Claim after P2P buy of a card with pending rows (owner switch mid-notify) | Disproven for claim path — uses current `owner_id` (Wave 0) | High |

### Wave 0 Results (2026-07-15)

- Pytest: `46 passed, 1 skipped` on transfer/wage/league/MoMD/audit/economy batch; plus select empty + factory OVR + evolution lifecycle green after remediations.
- Scheduler: `league_state_machine_job` cron once @ 00:05; `auto_sim_expired_fixtures_job` skips non-`legacy`.
- No `tick_evolution_match_progress` under `apps/`; friendly path writes `friendly_match_logs` only.
- No direct `players.coins` updates in cogs; no flat XP `15`.
- Schema verify + legacy OVR dry-run **not** run (no `DATABASE_URL` in session).
- Remediations shipped this implement: Select helper (H1), debug log removal (L1), evo PlayStyle copy + cooldown mirror 6h (H8).

### Backlog (non-blocking for v1 declare)

| ID | Note |
|----|------|
| M4 | Automation-on pilot: hub deadline + announce digest |
| M5 | App-layer expiry filter — accepted ponytail until RPC browse |
| M7 | Remove pilot Run Cycle after cron trusted on prod |
| H3 legacy | Dry-run `scripts/fix_inflated_player_stats.py` when DB available |
| H7 | Run `verify_required_schema.sql` against remote before ship |

### Wave 4 polish (2026-07-15 continued)

- M6 dual-ladder profile copy + league footer
- L2 full pytest green (injury ETA 016 anchors; squad swap fake hub)
- E10 Force End → Monday 00:05 when automation effective
- Remaining Medium edges E3/E6/E9/E11 + M1–M3 closed via code proof

### Prioritized Fix Sequence

| Wave | Focus | Exit gate |
|------|-------|-----------|
| **0 — Verify** | Re-run US-29 / progression / economy greps; reclassify C1–C5, H2, H4, H5, H7, H9, L1 | Registry statuses accurate; reopen any red items as Open |
| **1 — Money & races** | Bundles B-Transfer, B-Wages, B-League-Tick, B-Automation (Critical/High from Wave 0) | SC-001–SC-003 met; race tests green |
| **2 — Truth & match parity** | B-OVR, B-Match-Parity, B-Match-Stale, B-Evo-Truth, B-Retro (remaining High) | SC-004–SC-006 met |
| **3 — UX & recent edges** | B-UI-Select, B-Mentor, B-Hospital, E1–E12 prove/disprove | SC-007–SC-008 met; Select empty-state scripted pass |
| **4 — Polish & hygiene** | B-Copy, B-Hygiene, L* optional | Timeboxed; remaining Low → backlog |

Dependencies / bundles that should land together:

- **B-Transfer**: C1 + H4 + H9 + M5 + E4/E5
- **B-Wages**: C2 + M3 + E6/E7
- **B-League-Tick + B-Automation**: C3 + C4 + M4 + M7 + E8–E10 (one clock; admin gates)
- **B-OVR + B-Evo-Truth**: H3 + H8 (displayed truth)
- **B-UI-Select**: H1 alone is shippable early in Wave 3 if managers are blocked, but after money waves

### Key Entities

- **Issue Registry Entry**: ID, severity, module, symptom, expected behavior, status, bundle, remediation intent.
- **Remediation Wave**: Ordered work slice with exit gate tied to Success Criteria.
- **Feature Flag Pilot Checklist**: Per-flag smoke + race cases required before recommending broader enablement.
- **Intentional Non-Bug**: Documented behavior that must not be “fixed” without a new product spec.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Critical registry items are Closed or Verify-passed with a named automated/smoke check.
- **SC-002**: Concurrent transfer buy races produce ≤1 successful transfer and zero double-debits in QA runs (repeatable).
- **SC-003**: Payroll and MoMD retry simulations produce zero duplicate coin grants across ≥10 forced re-runs.
- **SC-004**: Sample of ≥50 newly generated cards show printed OVR = True OVR; progression allocate/claim sample shows no POT overshoot.
- **SC-005**: Bot/league/friendly reward contracts match published behavior in a scripted three-match-type checklist (friendly sandbox confirmed).
- **SC-006**: Evolution progress advances exactly once per card per resolved match in instrumented QA.
- **SC-007**: Scripted Select empty-state flows (hospital last discharge, marketplace zero filter, academy empty) show empty copy + recovery in ≥95% of checklist steps.
- **SC-008**: All E1–E12 edges are marked Proven / Disproven / Intentional with notes; any Proven High+ is Closed before calling v1.0.0 stable.
- **SC-009**: Managers in a short pilot pulse report fewer “bot ate my coins / menu vanished / wrong OVR” style complaints vs the pre-stability baseline cohort (target: majority “feels more trustworthy”).
- **SC-010**: No new slash commands, hubs, or tables introduced solely by this stability program unless required to close a Critical defect and documented here first.

## Assumptions

- US-29 match-loop hardening and many economy/XP pipes are already shipped; Wave 0 verifies rather than rewrites them blindly.
- Friendly matches remain intentional sandboxes (no XP/coins) unless a future product spec changes that.
- Feature flags (`transfer` peers, `wages_payroll_enabled`, `league_dynamics_enabled`, `league_automation_enabled`) stay **default off** until their Wave exit gates pass on a pilot guild.
- SelectMenu disappearance is treated primarily as empty-option / rebuild / timeout UX until a live Discord API defect with different root cause is reproduced.
- Historical OVR inflation may exist for pre-archetype cards; disposition is an ops decision inside H3, not silent ignore.
- This blueprint does **not** include public website (`008`) polish unless a stability defect blocks Discord play.
- Agent transcripts were not available for mining; inventory is rebuilt from SDD, AGENTS notes, research debt, change log themes, and the user’s named concerns — new live reports can append IDs without renumbering severities.
- Detailed file/RPC implementation plans belong in `/speckit.plan` for this feature; this spec defines the WHAT, priority, and acceptance bar.

## Out of Scope

- New gameplay features, new pack SKUs, bidding on transfers, wage auto-sell, PlayStyle grant evo phase (unless required only to stop false copy — then prefer copy fix).
- Broad economy rebalance / league prize retunes (separate calibration docs).
- Rewriting Discord.py or replacing Discord Select with web UI.
)
