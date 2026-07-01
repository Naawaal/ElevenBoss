# Milestone: V1 Match Engine + Manual Matchday Simulation

This document outlines the architecture, logic, and user flow for the first complete football match simulation system implemented in **ElevenBoss**.

---

## What Was Implemented

1. **Deterministic Match Engine:** Instantiated using a local `random.Random(seed)` generator ensuring deterministic, reproducible match simulations.
2. **Team Strength Calculations:** Dynamic calculation of Goalkeeper, Defense, Midfield, Attack, and Overall strengths based on the starting XI, incorporating position suitability and current fitness.
3. **Seeded xG Model:** Simulated match scores using expected goals (xG) based on team strengths and Poisson distribution sampling.
4. **Idempotency Protection:** Safe single-transaction matchweek simulations with job-locking keys to prevent duplicate runs.
5. **Lineup Fallback Handling:** Automatic validation of team lineups before matchday; automatically picks and saves the best starting XI if a manager forgot to set theirs.
6. **Components V2 Discord UI:** Rich interactive screens displaying matchweek status, simulated matchday results, and detailed match timeline reports.
7. **Standings Integration:** Automatic atomic updates to standings (Wins, Draws, Losses, Points, GF, GA, GD) with tie-breakers.

---

## Match Engine Model

The match engine (`app/engine/match_engine.py`) takes a seed and team inputs, calculates expected goals (xG), and sampling from a Poisson distribution generates:
- Home / Away goal counts.
- Goalscorer and assist attributions using position-weighted probabilities (ST/CF highest, GK near zero).
- Statistics (possession, total shots, shots on target).
- Timeline events (Match Start, Halftime, Goals, Yellow/Red Cards, Fulltime).
- Deterministic player match ratings between `3.0` and `10.0` based on match contributions.

---

## Team Strength Logic

Located in `app/engine/team_strength.py`:
- GK contributes to goalkeeper strength.
- LB, CB, RB, LWB, RWB contribute to defense strength.
- LM, RM, CM, CDM, CAM, LDM, RDM contribute to midfield strength.
- ST, CF, LW, RW contribute to attack strength.

Each starting player is evaluated using their base overall rating, fitness factor, and position suitability:
- **Natural Position:** Suitability modifier = `1.0`
- **Compatible Position:** Suitability modifier = `0.85`
- **Out of Position:** Suitability modifier = `0.6`
- **Outfield-in-Goal / Goalkeeper-outfield:** Suitability modifier = `0.2`

Player rating = `overall * suitability_modifier * (fitness / 100)`.
Team strengths are calculated as the average player rating in each position category. Home teams receive a small +5% boost to simulate home advantage.

---

## Idempotent Transaction Flow

Simulations run inside a single SQLAlchemy session (`app/services/matchday_service.py`):
1. **Acquire Job Lock:** Creates a record in `scheduler_runs` with key `matchday:{guild_id}:{season_id}:{week}` in `running` status. If already success/running, abort.
2. **Fetch and Lock Fixtures:** Fetches current week's fixtures using `with_for_update()`.
3. **Resolve Lineups:** Resolves home/away starting XI. If invalid, auto-picks using the squad players and saves it to prevent failure.
4. **Run Simulation & Save Results:** Computes the score, saves `MatchResult`, bulk inserts `MatchEvent`s, and marks the fixtures as `played`.
5. **Update Standings:** Updates points, played, goal differences, wins, losses, and draws atomically.
6. **Advance Season:** If it is the final week, marks the season and league as `completed`. Otherwise, increments `season.current_week += 1`.
7. **Complete Lock:** Sets job status to `success` and commits. Rolls back entirely on any exception.

---

## Commands Added

| Command | User Permissions | Description |
|---|---|---|
| `/matchday status` | Anyone | View current week matchday simulation status. |
| `/matchday run` | Administrators/Game Admins | Simulate all scheduled fixtures for the active week. |
| `/match recent` | Anyone | View stats and timeline of the most recently played match in the server. |
| `/match view <fixture_id>` | Anyone | View stats and timeline of a specific played match. |

---

## Components V2 UI Behavior

- **Matchday Status Screen:** Displays current week, total fixtures, scheduled vs played, and a status label (Ready, Played, Season Complete). Admins see the **Simulate Matchday** button.
- **Matchday Results Screen:** Shown after running simulation; lists all match scores and notes the advanced season week. Includes a **Recent Match Details** button.
- **Match Report Screen:** Shows possession %, shots, shots on target, MOTM, and chronological match events (goals, yellow/red cards).

---

## Next Milestone Recommendation

**Match Simulation Scheduling / Automatic Runner:**
- Implement a background cron task that runs simulations automatically on a set schedule.
- Implement player fitness recovery (players on the bench recover fitness, starters consume fitness).
- Implement training updates (players improve skills over time).
