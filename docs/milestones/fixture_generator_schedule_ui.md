# Milestone — Fixture Generator + Schedule UI

**Status:** Complete  
**Milestone Number:** 5  
**Date:** 2026-07-01

---

## What Was Implemented

This milestone introduces the full fixture scheduling system for ElevenBoss. Admins can generate a round-robin fixture schedule for the active season, and all users can browse the schedule by week through a Discord Components V2 UI.

**Scope:** Fixture generation, fixture persistence, fixture validation, fixture viewing, and fixture UI. No match simulation was implemented.

---

## Commands Added

| Command | Access | Description |
|---|---|---|
| `/fixtures generate` | Admin only | Generate the round-robin schedule for the active season |
| `/fixtures view` | All users | Show fixtures for the current season week |
| `/fixtures week week:3` | All users | Show fixtures for a specific week |

Button navigation is also fully supported:
- **◀ Prev** / **Next ▶** — Navigate to the previous/next week
- **📌 Current Week** — Jump back to the active season's current week
- **🔄 Refresh** — Reload the current week view
- **📅 View Fixtures** — Navigate from the generation success screen to the fixture list
- **◀ League / Locker Room** — Navigation back through the UI

---

## Round-Robin Algorithm

The fixture generator uses the classic **circle/polygon rotation algorithm**.

### How it works

For N clubs (must be even), one club is fixed at position 0 and the remaining N-1 clubs rotate around it across N-1 rounds:

```
Round k (0-indexed):
  ring[0] = club_ids[0]  (fixed)
  ring[i] = club_ids[((i - 1 + k) % (n - 1)) + 1]  for i in 1..n-1

Pairings:
  (ring[0], ring[n-1])
  (ring[1], ring[n-2])
  ...
  (ring[n//2 - 1], ring[n//2])
```

Home/away is alternated by round parity to balance scheduling.

### Properties guaranteed

- Every club plays **exactly once per week**
- No club plays **itself**
- No **duplicate pairings** in single round-robin
- Every pair plays **exactly once**
- Generation is **deterministic** for the same club order
- **Weeks numbered from 1**

### Supported sizes (single round-robin)

| League Size | Weeks | Per Week | Total Fixtures |
|---|---|---|---|
| 8 clubs | 7 | 4 | 28 |
| 10 clubs | 9 | 5 | 45 |
| 12 clubs | 11 | 6 | 66 |
| 16 clubs | 15 | 8 | 120 |

---

## Single vs Double Round-Robin

For V1, **single round-robin** is always used. Every club pair plays once.

Double round-robin is implemented in the engine (`double_round_robin=True`) and its tests are included, but the parameter is not exposed to users or the service yet. When enabled:

- The second half reverses home/away for every fixture
- Week count doubles, total fixtures double
- The second half weeks are offset by `n-1` from the first half

---

## Fixture Lifecycle

```
SCHEDULED → (future milestones) → LOCKED → SIMULATING → PLAYED
                                                       ↘ VOID
```

All generated fixtures start as `SCHEDULED`. Future milestones will implement the transition to `LOCKED`, `SIMULATING`, and `PLAYED`.

---

## Database Persistence

All fixtures are inserted in a single atomic transaction using `get_session()` from `app/db/session.py`. If any step fails (validation, generation, or insert), the session rolls back automatically and no partial data is persisted.

The `fixtures` table was already present (defined in `app/models/fixture.py`). No new migration was required.

Unique constraint `UNIQUE(season_id, week, home_club_id, away_club_id)` prevents duplicate fixture rows at the database level as a defense-in-depth measure. The service also checks for existing fixtures before inserting.

---

## Validation Rules

### `/fixtures generate`
1. Must be run inside a guild
2. User must have Discord administrator permission or configured game admin role
3. An active league must exist (`status = ACTIVE`)
4. An active season must exist for that league
5. Fixtures must not already exist for this season
6. At least 2 clubs must be assigned to the season
7. Club count must be even (guaranteed by league sizes 8/10/12/16)

### `/fixtures view`
1. Must be run inside a guild
2. Active league and active season must exist
3. Returns a friendly message if fixtures have not been generated yet

### `/fixtures week`
1. Must be run inside a guild
2. Week must be ≥ 1
3. Week must be within the valid range for the season (`min_week` to `max_week`)
4. Returns a friendly error with the valid range if out of bounds

---

## Components V2 UI

### Generation Success Screen

```
📅 FIXTURE SCHEDULE GENERATED
League: Pro League
Season: Season 1

📊 Summary
👥 Total Clubs: 8
📆 Total Weeks: 7
⚽ Fixtures Per Week: 4
🗂️ Total Fixtures: 28
▶️ Current Week: Week 1

[📅 View Fixtures] [📊 View Table] [◀ League] [🏠 Locker Room] [✖ Close]
```

### Fixture List Screen (Week X)

```
⚽ FIXTURES — Week 3 of 7
League: Pro League  |  Season: 1
Current Week: Week 1

Fixtures (4):
🕐 FC Alpha vs FC Beta  ·  Scheduled
🕐 Rangers FC vs City United  ·  Scheduled
...

[◀ Prev] [Next ▶] [📌 Current Week] [🔄 Refresh] [✖ Close]
[◀ League] [🏠 Locker Room]
```

The `◀ Prev` button is disabled on week 1. The `Next ▶` button is disabled on the final week.

---

## Architecture

```
app/engine/fixture_generator.py    ← Pure round-robin algorithm
app/repositories/fixture_repository.py  ← DB queries
app/repositories/league_repository.py   ← Added: get_active_league_by_guild
app/repositories/season_repository.py   ← Added: get_active_season_for_league
app/services/fixture_service.py    ← Business logic + atomic transaction
app/ui/renderers/fixture_renderer.py    ← View models + data mapping
app/ui/layouts/fixtures.py         ← Components V2 payload builders
app/ui/handlers/fixtures_handler.py     ← Session + permission orchestration
app/cogs/fixtures_cog.py           ← Discord slash commands
```

Also modified:
- `app/repositories/__init__.py` — new exports
- `app/ui/custom_ids.py` — added `fixtures` scope, `week`/`prev`/`next`/`generate` actions
- `app/ui/handlers/__init__.py` — new exports
- `app/cogs/club_cog.py` — routing for `fixtures` scope in `on_interaction`

---

## Tests Added

| Test File | Coverage |
|---|---|
| `tests/test_fixture_generator.py` | Engine: counts, rules, determinism, edge cases, double RR |
| `tests/test_fixture_service.py` | Service: all validation cases, rollback, current week, invalid week |
| `tests/test_fixture_ui_payloads.py` | UI: layouts render, disabled buttons, empty state, club names |

Run with:
```bash
python -m pytest tests/test_fixture_generator.py tests/test_fixture_service.py tests/test_fixture_ui_payloads.py -v
```

---

## Known Limitations

1. **Fixtures are never marked as played** — the `status` stays `SCHEDULED` until the match engine milestone is implemented.
2. **`current_week` is never advanced** — Season's `current_week` is always `1` after generation. Advancing it is part of the matchday automation milestone.
3. **Odd club counts are rejected** — V1 only supports even league sizes. An odd count from a corrupted state would fail gracefully.
4. **No fixture image renderer** — Fixture lists use text-only formatting. A visual grid image could be added in a later milestone.
5. **Club name relationship loading** — The renderer reads `fixture.home_club.name` via SQLAlchemy's lazy loading. For very large fixture sets, explicit eager loading would be more efficient.

---

## Next Recommended Milestone

**Milestone 6 — Match Simulation Engine**

Recommended scope:
- Implement a deterministic match simulation engine in `app/engine/match_simulator.py`
- Simulate individual matches based on club/player ratings and a seed
- Produce match results with scorelines, goalscorers, and basic events
- Persist results to the `match_results` and `match_events` tables
- Update `LeagueStanding` records from match results
- Advance `Season.current_week` after each matchday
- Add `/simulate` admin command to trigger a matchday manually

Pre-requisites already complete: Fixture table ✅ | Standing table ✅ | Rating system ✅ | Match model ✅
