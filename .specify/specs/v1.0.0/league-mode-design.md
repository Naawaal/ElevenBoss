# ElevenBoss Immersive League Mode — Definitive Design Guide

**Status:** Approved for v1.0.0 implementation (US-26)  
**Related:** [`spec.md`](spec.md) US-26, [`plan.md`](plan.md) § League Mode v2

---

## Overview

Transforms the guild seasonal league from a bare-bones loop into the bot's flagship competitive mode. Fixes economy v2 / match XP regressions, decouples weekly division points from seasonal fixture standings, and layers immersive matchday UX on the existing NSS engine + League Journal.

**Recommended pacing:** 4–6 real-world weeks, matchday every 2–3 days, 48h play windows, auto-sim at window end.

---

## Competitive Research Summary

| Pattern | Source | ElevenBoss adoption |
|---------|--------|---------------------|
| 8–12 club round-robin | Hattrick, OSM | Existing 8/10/12/16 sizes |
| Simultaneous matchdays + async window | OSM | `window_start`/`window_end` + auto-sim |
| Live journal commentary | Top Eleven | `#league-journal` + ticker |
| Weekly milestone rewards | EA FC Rivals | Matchday point thresholds |
| Promotion drama + ceremony | Hattrick | Season-end awards + archive |
| Discord-native social | OSM | League channel + matchday threads |
| FM-lite prep | Football Manager | Lineup familiarity, opponent scout |

**Rejected:** mandatory live attendance, 15+ matches/week, FM scouting UI, paid league creation, 16-week seasons.

---

## Architecture: Decoupled League Systems

1. **Guild Seasonal League** — `league_fixtures` → `fetch_standings()` (source of truth for hub table)
2. **Weekly Division Ladder** — `players.league_points` fed **only by bot matches**; Monday reset via `weekly_league_reset_job`

League matches must **not** write `players.league_points` or `players.goal_difference`.

---

## User Story Priorities

### Must-Have (Phase 0–1)
- Hub dashboard: rank, next opponent, countdown, form string
- Economy v2 + match XP 1.25× for league matches
- 11-player XI guard
- Standings with form + tie-break footer
- Matchday DMs (6h warning)

### Should-Have (Phase 2–3)
- Opponent scout embed
- Live as-it-stands table in journal
- **Dual threads (US-28):** `📊 League Journal` (standings + results) + `🎙️ MatchDay` (commentary), locked at season start
- Season prizes RPC + trophy cabinet on profile
- Pitch pre-match images in MatchDay thread

### Nice-Have (Phase 4–5 + future)
- Weekly milestones, familiarity bonus, post-match reactions
- Admin season config (size, OVR cap, entry fee, pause)
- Multi-division guild pyramid, Winners Cup

---

## Schema (migration 032)

- `league_seasons.config_json`, status values: `registration`, `active`, `paused`, `completed`
- `league_season_awards` — per-season award rows
- `player_league_history` — trophy cabinet
- RLS on `league_fixtures`, `league_seasons`, `league_participants`, `match_logs`, `player_season_stats`
- RPC `distribute_season_prizes(p_season_id)`
- `game_config` keys: `league_*` tunables

---

## Rewards

**Per match:** `apply_club_economy` + `build_process_match_result_rpc(match_type='league')` + `sync_action_energy`

**Season end:**

| Finish | Pool share |
|--------|------------|
| 1st | 60% |
| 2nd | 25% |
| 3rd | 10% |
| 4th+ | participation coins |

---

## Rollout Phases

| Phase | Scope |
|-------|-------|
| 0 | Trust fixes: economy, XP, energy, XI guard, decouple points, RLS |
| 1 | Hub UX: dashboard, form, scout, registration countdown |
| 2 | Matchday spectacle: pitch images, live table, matchday threads |
| 3 | Season lifecycle: prizes, awards, trophy cabinet |
| 4 | Engagement: milestones, familiarity, reactions, DMs |
| 5 | Admin config: season settings modal |
