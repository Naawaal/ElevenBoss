# Contract: Fixture Resolution & Assistant Manager

**Feature**: `026-league-lifecycle-rulebook`

## Pipeline

```text
deadline or manual early trigger
  → acquire fixture lease / operation_key fixture:{id}:resolve
  → lock both clubs (match_locks)
  → resolve lineups (priority below)
  → both legal → create match run with stored seed → simulate → settle
  → one illegal → 3-0 forfeit settle
  → both illegal → double_forfeit settle
  → mark fixture terminal
  → outbox result event
  → check matchday completion
```

## Lineup priority

1. Valid submitted matchday lineup  
2. Valid saved league lineup  
3. Assistant-repaired lineup (replace injured/suspended; fill empties; preferred formation; best eligible bench; preserve tactics)  
4. Emergency legal lineup  
5. Forfeit if no legal team  

### V1 wiring note (hub / squad — no new slash commands)

- **Saved plan source**: `/squad` formation + `squad_assignments` slots 1–11 (fetched via `fetch_squad_xi`).
- **Submitted matchday lineup**: not a separate Discord surface or table in V1 — `submitted_starters=None` in `select_lineup_plan`. Managers prepare via existing `/squad` and play early via `/league` Match Center.
- **Deadline path**: `league_lifecycle_engine._resolve_club_lineup_plan` → `select_lineup_plan` over owned `player_cards` pool; repaired/emergency starter ids passed into `run_league_match_simulation(..., home_card_ids=/away_card_ids=, skip_xi_gate=True)`.
- **Early play**: same `run_league_match_simulation` settle fields (`result_type`, `match_seed`, `status`) — no first-click standings advantage.

## Forfeit outcomes

| Case | Score | Points | Extras |
|------|-------|--------|--------|
| One illegal | 3–0 vs illegal | W=3 / L=0 | Normal forfeit; `result_type=forfeit` |
| Both illegal | 0–0 | **0 / 0** | MP+1, L+1 both; GF/GA/GD 0; `result_type=double_forfeit`; **not** draw, clean sheet, unbeaten, appearance, or promo-eligible match |

## Infrastructure vs sport

- Discord down → still settle; publish via outbox later.  
- Match engine down → `failed_retryable`; **never** forfeit for infra.  
- Early presentation → same sporting rules as deadline path (no first-click standings advantage).

## Reproducibility

```text
seed = hash(season_id, fixture_id, match_engine_version)
```

Persist seed, engine_version, ruleset_version, squad/tactical snapshots, result hash. Recovery resumes or reproduces — never conflicts.
