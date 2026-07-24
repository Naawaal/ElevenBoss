# Contract: Bot Soak Gate & Rollback

**Feature**: `044-match-v3-rollout`

## Bot soak criteria (must pass before `match_engine_v3_league=1`)

| # | Criterion |
|---|-----------|
| 1 | `041` V3 pytest suite green on the deploy branch (`determinism`, `golden_corpus`/`projectors`, win-rate band as applicable) |
| 2 | ≥ **20** completed bot matches with `match_runs.engine_version = 'nss_v3'` in soak environment |
| 3 | Zero double-settle / duplicate coin-XP incidents attributable to V3 in that window |
| 4 | Spot-check: explainability field appears on a sample of V3 bot finals when stream has goals/chances |
| 5 | Rollback drill: set `match_engine_v3_bot=0`; new bot kick pins `nss_v2`; any in-flight v3 run still completes |

## League enable

Only after soak criteria checked. Then enable `match_engine_v3_league` and validate:

- One live Play fixture settles standings once  
- One auto-sim fixture settles once  
- Pause/resume / matchday lock behavior unchanged in intent  

## Friendly

Default remains off through bot+league soak unless explicitly justified.

## Monitoring (lightweight)

During first 14 days of bot soak: watch support for “double paid / vanished coins”; abort further flag expansion if attributed to V3 cutover.

---

## Ops status (implementation)

| Gate | Status (2026-07-24) |
|------|---------------------|
| Code: pin / create-run / explainability enrichment | **Ready** — ship with bot |
| Pytest soak criteria #1 | Run before enabling; see quickstart |
| Staging bot flag enable + ≥20 matches (#2–4) | **Bot flag ON** (2026-07-24); Discord soak in progress — see [ops-soak-log.md](../ops-soak-log.md) |
| Rollback drill (#5) | **Done** (bot off → on via ops script) |
| `match_engine_v3_league=1` | **Blocked** until ≥20 completed bot `nss_v3` |
| Friendly V3 | Left at `0` (T027 skipped) |

Code implementation does **not** flip production `game_config` flags.
