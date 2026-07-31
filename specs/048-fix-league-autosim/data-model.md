# Data Model: Expired Fixture Settle (`048`)

**Storage**: No new tables. Uses existing `league_fixtures` sporting fields.

## `league_fixtures` (relevant fields)

| Field | Role |
|-------|------|
| `window_end` | Expired when `< now` |
| `is_played` | Terminal played flag |
| `home_score` / `away_score` | Result |
| `status` | e.g. `settled`, `forfeit`, `failed_retryable` |
| `result_type` | `settled` \| `forfeit` \| `double_forfeit` \| … |
| `resolved_by` | `auto_sim` \| `manual` (064 CHECK; forfeit uses `auto_sim` + `result_type`) |
| `played_at` | Settle timestamp |

## Logical settle modes

| Mode | When | Writes |
|------|------|--------|
| `sim` | Both sides eligible | Existing auto-sim path → `is_played`, scores, `resolved_by=auto_sim` |
| `forfeit` | Exactly one human side ineligible | 3–0 / 0–3 via `single_forfeit` |
| `double_forfeit` | Both human sides ineligible | 0–0 via `double_forfeit` |
| `skip_infra` | Guild unreachable / active run | No sporting write |

## Eligibility (human)

Same as match gate: `human_club_xi_ok` → incomplete XI, `squad_invalid`, or past-grace contracts in Starting XI.

AI: always eligible for this feature’s decision matrix.

## Standings

Season standings continue to aggregate **played** fixtures via `apply_fixture_to_row` (already understands `double_forfeit`). No denormalized standings table required for this fix.

## State transitions

```text
[expired, is_played=false]
    ├─ infra / active run → unchanged (retry later)
    ├─ both eligible → auto_sim → played
    ├─ one ineligible → forfeit → played (result_type=forfeit)
    └─ both ineligible → double_forfeit → played
```
