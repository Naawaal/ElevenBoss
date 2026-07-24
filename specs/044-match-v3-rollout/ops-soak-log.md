# Ops soak log — Match Engine V3 (044)

**Updated**: 2026-07-24

## Flag state (DB)

| Key | Value | Notes |
|-----|-------|-------|
| `match_engine_v3_bot` | **1** | On |
| `match_engine_v3_league` | **1** | Enabled 2026-07-24 per owner request (soak gate overridden) |
| `match_engine_v3_friendly` | **1** | Enabled 2026-07-24 per owner request |

Helper: `python scratch/ops_match_v3_rollout.py status|enable-bot|rollback-drill|enable-league|disable-league`

## Completed ops tasks

| Task | Result |
|------|--------|
| T010 enable bot | OK — bot=1, league=0, friendly=0 |
| T012 rollback drill | OK — bot briefly set to 0 then re-enabled to 1 |
| T013 re-enable for soak | OK — bot remains 1 after drill |
| T027 friendly V3 | Skipped — leave at 0 (no product need) |
| Live pin smoke | OK — `python scratch/smoke_match_v3_pin.py` (bot→`nss_v3`, friendly→`nss_v2`, runs abandoned) |
| Bot restart | OK — Discord bot restarted 2026-07-24 so process cache is fresh |

## Soak counts (at log time)

- Completed bot `nss_v3` runs: **1** (gate **≥20**) — no new *completed* Discord soaks yet after flag enable
- League enable gate: **BLOCKED**

## Your next steps (Discord — cannot automate)

1. ~~Restart the Discord bot~~ **done**
2. **T011**: Play ≥3 `/battle` bot matches. After each, confirm Decision Windows / styles and post-match **How it was decided**.
3. SQL check: `python scratch/ops_match_v3_rollout.py status` — latest bot runs should show `engine=nss_v3`.
4. **T026**: While bot V3 is on, play one friendly — must stay sandbox (no coins/XP); pin `nss_v2` while friendly flag is 0. *(Pin already verified by smoke; Discord sandbox footer still needs a human play.)*
5. Continue until **≥20** completed bot `nss_v3` matches with no double-settle.
6. Then **T020** sign-off → `python scratch/ops_match_v3_rollout.py enable-league` → **T023** live + auto-sim smoke.

## Contingency

- League incident: `python scratch/ops_match_v3_rollout.py disable-league` (T024)
