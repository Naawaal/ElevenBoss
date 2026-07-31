# Flag maturity checklist (050 US7)

Track temporary flags until soak gates pass. **Do not** remove V2 / Mentor env in the same deploy as hot-path RPCs.

| Flag / key | Location | introduced_at | remove_after | owner | rollback |
|------------|----------|---------------|--------------|-------|----------|
| `MENTOR_TRANSFUSION_ENABLED` | env + `development_cog._mentor_enabled` | 2026-06 (mentor ship) | After 14d stable mentor usage post-default-on | eng | Set env `0` |
| `match_engine_v3_bot` | `game_config` / `match_runs.resolve_engine_version` | 044/NSS V3 | After soak metrics green + V2 drain | eng | Config `0` forces V2 |
| `match_engine_v3_friendly` | same | 044 | same | eng | same |
| `match_engine_v3_league` | same | 044 | same | eng | same |
| `league_dynamics_enabled` | `game_config` / league jobs | pre-050 | After audit vs lifecycle workers (T056) | eng | Config off |
| `league_automation_enabled` | `guild_config` + economy helpers | pre-050 | After T056 consolidation | eng | Guild/config off |

## Soak exit criteria (before T052–T054)

1. V3 completion / recovery / settlement error rates within agreed band (link `044` notes).
2. No active recoverable V2 runs (T053–T054).
3. Mentor path stable with flag default on for agreed window (T055).

## Separate deploys

1. Hot-path / cache (US3–US6)  
2. V3 default flip (T052)  
3. V2 code removal (T054)  
4. Mentor env removal (T055)
