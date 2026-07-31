# Ops: 050 US7 V3 soak log

**Updated**: 2026-07-31  
**Parent**: [flag-maturity-checklist.md](./contracts/flag-maturity-checklist.md) · [044 ops-soak-log](../044-match-v3-rollout/ops-soak-log.md)

## Environment snapshot (DATABASE_URL at log time)

| Check | Result |
|-------|--------|
| 050 RPCs 090/093 | Present (`check_050_us7_soak_ready.py`) |
| Measured indexes 091/092 | Present; bare `idx_players_division` absent |
| `match_engine_v3_bot` | **1** |
| `match_engine_v3_friendly` | **1** |
| `match_engine_v3_league` | **1** |
| Staged level | **Stage 3/3** (flags already all-on from 044 override 2026-07-24) |
| Completed `nss_v3` all-time | bot **335**, friendly **88**, league **7** |
| Recent bot pins | `nss_v3` (2026-07-31) |

## Agreed soak window

| Field | Value |
|-------|-------|
| Window start | 2026-07-31 (050 hot-path + indexes live; V3 flags already 1) |
| Target exit review | After ≥14d **or** owner sign-off with `soak-report` green |
| Load tests | **Blocked** until after T052+ canonical V3 |

## Commands

```bash
python scratch/check_050_us7_soak_ready.py
python scratch/ops_match_v3_rollout.py status
python scratch/ops_match_v3_rollout.py soak-report --days 14
# rollback one mode without deleting V2:
python scratch/ops_match_v3_rollout.py rollback-mode bot|friendly|league
```

## Human smoke (post 090–093 deploy)

- [ ] `/development` / skills / mentor  
- [ ] `/leaderboard` division + global ordering  
- [ ] Transfer Board filters/page  
- [ ] `/admin` → Performance (cache hit, no 429/5xx spike)  
- [ ] Bot match settles XP/coins/fatigue once  
- [ ] Friendly sandbox (no economy)  
- [ ] League live + auto-sim settle once each  

## Latest soak-report (14d, 2026-07-31)

| Mode | Engine | Completed / total | Failed | Abandoned | avg dur s | avg goals |
|------|--------|-------------------|--------|-----------|-----------|-----------|
| bot | v3 | 335/343 (97.7%) | 0 | 8 | 60.0 | 3.37 |
| bot | v2 | 343/345 (99.4%) | 0 | 2 | 57.2 | 3.50 |
| friendly | v3 | 88/88 (100%) | 0 | 0 | 50.7 | 1.77 |
| league | v3 | 7/7 (100%) | 0 | 0 | 48.0 | 3.29 |
| league | v2 | 12/20 (60%) | 0 | 8 | 46.6 | 2.75 |

In-flight recoverable: **none**. Watch bot V3 abandon rate vs V2; grow league V3 sample before exit.