# Flag maturity checklist (050 US7)

Track temporary flags until soak gates pass. **Do not** remove V2 / Mentor env in the same deploy as hot-path RPCs (090–093).

| Flag / key | Location | introduced_at | remove_after | owner | rollback |
|------------|----------|---------------|--------------|-------|----------|
| `MENTOR_TRANSFUSION_ENABLED` | env + `development_cog._mentor_enabled` | 2026-06 (mentor ship) | After 14d stable mentor usage post-default-on | eng | Set env `0` |
| `match_engine_v3_bot` | `game_config` / `match_runs.resolve_engine_version` | 044/NSS V3 | After soak metrics green + V2 drain | eng | Config `0` forces V2 |
| `match_engine_v3_friendly` | same | 044 | same | eng | same |
| `match_engine_v3_league` | same | 044 | same | eng | same |
| `league_dynamics_enabled` | `game_config` / league jobs | pre-050 | After audit vs lifecycle workers (T056) | eng | Config off |
| `league_automation_enabled` | `guild_config` + economy helpers | pre-050 | After T056 consolidation | eng | Guild/config off |

---

## Precondition (before US7 flag work)

1. Deploy migrations **090–093** (+ **091/092** indexes) to soak env.
2. Smoke: `/development`, skills, mentor, `/leaderboard`, Transfer Board, `/admin` → Performance.
3. Confirm: no migration drift (`scratch/check_050_us7_soak_ready.py`), sane cache metrics, no DB error/retry spike, LB/market ordering OK.

**Do not** start load scripts in this phase.

---

## Staged V3 soak (T051) — separate from hot-path deploy

| Stage | Action | Command |
|-------|--------|---------|
| 1 | `match_engine_v3_bot = 1` (friendly/league off) | `python scratch/ops_match_v3_rollout.py stage1-bot` |
| 2 | `match_engine_v3_friendly = 1` | `… stage2-friendly` |
| 3 | `match_engine_v3_league = 1` | `… stage3-league` (gate: ≥20 completed bot `nss_v3`, or `--force`) |

Keep **V2 executable** entire soak (`flag=0` rolls new kicks to `nss_v2`). **Do not delete V2** (T054 later).

Per-mode metrics (record via `… soak-report [--days 14]`):

- match completion rate  
- settlement failures (failed status + support double-pay)  
- recovery failures / stuck `streaming`/`completing`  
- average simulation duration (`started_at` → `completed_at`)  
- invalid event/state errors (logs / Sentry)  
- score distribution (avg/min/max goals)  
- match-lock incidents (manual/support)  
- post-match XP/economy/fatigue settlement errors  

Also see `specs/044-match-v3-rollout/contracts/soak-and-rollback.md` and `ops-soak-log.md`.

### Exit criteria (before T052–T054)

```text
All three V3 modes enabled
No integrity/settlement regressions
No unresolved V3 recovery bugs
No meaningful latency regression
No need to roll back for an agreed soak window
```

### After exit (separate deploys — not this slice)

```text
V3 becomes default (T052)
→ stop creating new V2 runs (T053)
→ preserve V2 read/recovery compatibility
→ wait until no active/recoverable V2 runs remain
→ delete V2 execution path (T054)
→ Mentor env removal (T055)
→ league flag audit (T056)
```

## Separate deploys

1. Hot-path / cache / measured indexes (US3–US6 + 091/092)  
2. V3 staged soak flags only (T051) — **current**  
3. V3 default flip (T052)  
4. V2 code removal (T054)  
5. Mentor env removal (T055)
