# Feature Specification: League Season Pause / Resume Fix

**Feature Branch**: `037-league-pause-resume`

**Created**: 2026-07-22

**Status**: Draft

**Parent**: `specs/029-game-integrity` (US-42) | Related: `034-league-integrity` (US-42.5), `026-league-lifecycle-rulebook`, `027-league-autonomous-admin`

**Input**: User description: "Issue in league hub — why am I seeing league is paused: ⏸️ Season Paused — matchdays are frozen until the server is available again…"

## Analysis Verdict *(investigation result)*

**Likely bug: pause without resume wiring.**

| Observation | What the code does today |
|-------------|--------------------------|
| Hub shows paused copy | `league_cog.build_hub_embed` returns early when `season.status == "paused"` with the exact message the user reported |
| Seasons enter `paused` | `pause_league_season` / `pause_season_if_guild_unreachable` (guild NotFound/Forbidden during auto-sim), or `pause_seasons_for_guild` on `on_guild_remove` |
| Seasons leave `paused` | `resume_season` **exists** in `league_lifecycle_engine.py` (rebase windows + `status = active`) but has **no production call site** in `apps/discord_bot/` |
| Lifecycle sweeper | `process_due_transitions` handles `active`, `registration_*`, `preparing`, `completed` — **skips `paused` entirely** |
| Hub open | `/league hub` loads season and renders embed; **does not** attempt resume when guild is reachable |

**User impact**: A manager opens `/league hub` in a guild where the bot is present (e.g. "Pixel Portal") and sees a stranded **Season Paused** banner even though the server is available. Matchdays stay frozen until something external sets `status` back to `active` — which nothing currently does automatically.

**Intentional pause behavior (034 / 026)**: Infrastructure outage should pause, not forfeit. On recovery, windows rebase forward. That recovery step is **specified but not shipped** for the common "guild is back" path.

**Not the same as**: No season (`status` absent), registration phase, or admin Discord pause/resume (removed per 027 — ops/engine only).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Hub shows active season when server is available (Priority: P1)

A manager opens the Seasonal League Hub in a guild where the bot is present and the season was only paused due to a past transient outage or auto-sim guild-resolve failure. The hub should show the normal matchday dashboard (standings, fixtures, Play), not a permanent paused banner.

**Why this priority**: This is the reported symptom — false or stranded pause blocks all league play.

**Independent Test**: Set a season to `paused` with `pause_started_at` set while bot is in guild; open `/league hub` → season resumes (or hub triggers resume) and shows matchday UI.

**Acceptance Scenarios**:

1. **Given** a season `paused` with valid `pause_started_at` and the bot can resolve the guild (cache or API), **When** the manager opens `/league hub`, **Then** the season transitions to `active`, matchday windows are rebased by pause duration, and the hub shows matchday content (not the paused-only embed).
2. **Given** the same recovery, **When** the manager uses Play on an open fixture, **Then** league match flow proceeds (not blocked by paused status).
3. **Given** resume succeeds, **When** the manager re-opens the hub, **Then** `status` remains `active` and paused copy does not return.

---

### User Story 2 — Legitimate pause still blocks play (Priority: P1)

When the bot truly cannot reach the guild (removed, NotFound, Forbidden), the season stays paused and managers see clear copy — not a silent failure or admin-only "wait for admin" message.

**Why this priority**: 034 requires infrastructure pause without sporting forfeits; we must not "fix" stranded pause by removing real pause.

**Independent Test**: Bot not in guild (or simulated confirmed unreachable) → hub stays paused; Play blocked with pause reason.

**Acceptance Scenarios**:

1. **Given** the bot is confirmed not in the guild, **When** the manager opens the hub, **Then** the season remains `paused` and copy explains play is frozen until the server is available again.
2. **Given** a paused season and confirmed unreachable guild, **When** the manager attempts Play, **Then** they receive a blocked message (not a raw error).
3. **Given** a transient Discord 429/5xx during guild resolve, **When** pause is evaluated, **Then** the season is **not** newly paused solely for transient errors (existing `resolve_bot_guild` contract).

---

### User Story 3 — Hub honesty during pause (Priority: P2)

If the season is still legitimately paused, the hub explains *why* and *since when* in manager-friendly terms (not only generic frozen text).

**Why this priority**: Trust and supportability when pause is real.

**Independent Test**: Force paused + unreachable → hub shows paused state with elapsed pause duration or "since" timestamp.

**Acceptance Scenarios**:

1. **Given** a legitimately paused season, **When** the hub is shown, **Then** copy includes that matchdays are frozen and windows will extend on resume (existing intent).
2. **Given** `pause_started_at` is set, **When** still paused, **Then** the hub surfaces how long the season has been paused (relative or absolute timestamp).

---

### Edge Cases

- Season paused with **null** `pause_started_at` (legacy bad row): resume must not corrupt windows; fail safe with ops-visible log and hub copy that does not claim auto-recovery succeeded.
- **Legacy dynamics** seasons (non-`lifecycle_v1`): auto-sim path can pause via `auto_sim_expired_fixtures`; resume behavior must cover the same stranded-pause class or document grandfather exception.
- **Bot removed then re-invited**: season may have been paused with `bot_removed`; on rejoin, auto-resume when guild reachable.
- **Double hub open / concurrent resume**: idempotent — second resume is a no-op.
- **Paused during registration** vs **active**: resume returns to the correct prior open status (`active`, or registration phase if that was paused — clarify in plan; default: restore to status before pause if tracked, else `active` for matchday seasons).
- V1 lifecycle sweeper and hub resume must not fight (single `resume_season` entry point).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the bot can **confirm** the guild is reachable, the system MUST attempt to **resume** a `paused` season for that guild using the shared `resume_season` semantics (rebase unresolved windows, set `active`, clear `pause_started_at`, accumulate `total_paused_seconds`).
- **FR-002**: Resume MUST be triggered from at least one **automatic** path managers hit in normal play (e.g. `/league hub` open and/or lifecycle sweeper) — not only manual DB edits.
- **FR-003**: When the guild is **confirmed unreachable**, the season MUST remain `paused` and hub/Play MUST block with clear pause copy.
- **FR-004**: Transient Discord errors (429, 5xx) during guild resolve MUST NOT cause a new pause (preserve `resolve_bot_guild` behavior).
- **FR-005**: Hub embed MUST NOT show the paused-only view when the season has successfully resumed in the same request flow.
- **FR-006**: `process_due_transitions` (or equivalent sweeper) MUST either resume reachable paused seasons or delegate to the same resume helper — paused seasons must not be silently ignored forever.
- **FR-007**: Resume MUST be idempotent and safe under retry (no double rebase on duplicate calls).
- **FR-008**: No new Discord admin pause/resume commands (027 policy); ops recovery remains engine-level.
- **FR-009**: Sporting rules unchanged — pause still does not bulk-forfeit fixtures; resume only rebases time windows per `026` / `034` contracts.

### Key Entities

- **League Season**: `league_seasons` row with `status`, `pause_started_at`, `total_paused_seconds`, `current_matchday`, etc.
- **Guild reachability**: Bot membership / API resolve result (`resolve_bot_guild`).
- **Seasonal League Hub**: `/league hub` embed and navigation (`league_cog.py`).
- **Pause / Resume**: `pause_league_season` / `resume_season` engine pair.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of scripted cases where season is `paused`, bot is in guild, and `pause_started_at` is set, opening `/league hub` results in `status = active` and rebased windows within one hub interaction.
- **SC-002**: In 100% of scripted unreachable-guild cases, hub remains paused and Play stays blocked.
- **SC-003**: Zero production reports of "Season Paused" persisting after bot is visibly online in the guild for >5 minutes following fix deploy (qualitative regression target).
- **SC-004**: `resume_season` has at least one traced call site in `apps/discord_bot/` (grep / integrity test).
- **SC-005**: Paused seasons are processed by automation within one sweeper cycle when guild becomes reachable (if sweeper path is chosen).

## Assumptions

- The user's guild ("Pixel Portal") has a season row with `status = paused` — most likely from a past `guild_unreachable` or `bot_removed` pause that never resumed.
- Fix is **resume wiring + hub/sweeper trigger**, not removing pause feature entirely.
- `pause_started_at` is set on pauses after 034 helper work; rows with null may need backfill or guarded resume (plan phase).
- V1 and legacy dynamics may both need resume entry points; legacy uses `auto_sim_expired_fixtures` pause path today.
- Discord admin pause/resume buttons stay removed per 027; auto-resume on reachability is system behavior, not admin action.

## Out of Scope

- Redesigning league calendar or matchday rules (`026` content).
- New slash commands or admin hub buttons for pause/resume.
- Changing prize/settlement idempotency (034 other stories).
- Investigating unrelated hub title formatting ("Pixel Portal Seasonal League Hub" is expected `{guild.name}` pattern).
