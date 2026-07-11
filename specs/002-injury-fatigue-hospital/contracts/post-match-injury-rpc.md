# Contract: Post-match injury RPC (Phase 2)

## When

After `apply_match_fatigue` on competitive bot/league matches. Skip friendlies.

## Pure roll (Python → payload)

**Eligibility (LOCKED A+C):**
- Only starters with `fatigue < 75` may roll.
- At most **one** injury applied per club per match: iterate eligible starters in stable XI order; on first successful roll, stop and emit that single injury (do not continue rolling).

Per eligible starter until first hit:

```text
Base_Chance = 0.4%
Fatigue_Modifier = (100 - Fatigue) * 0.04%
Age_Modifier = max(0, (Age - 30) * 0.15%)
PHY_Protection = max(0, (PHY - 70) * -0.02%)
Injury_Chance = Base + Fatigue + Age + PHY_Protection
```

Tier weights: 1–60 Minor, 61–90 Moderate, 91–100 Major (**roll 100 = Major**, not career-ending).

Base recovery days: Minor 3, Moderate 8, Major 20.

If no eligible starters or all rolls miss → empty `p_injuries` array (still call RPC or skip — prefer skip if empty).

## RPC: `process_post_match_injuries(p_owner_id, p_injuries jsonb)`

**Input element**: `{ "player_card_id": uuid, "tier": 1|2|3 }`

**Behavior**:

1. Read `hospital_level`; `max_beds = hospital_level + 1`.
2. Count active `hospital_patients` for owner.
3. For each injury (in order):
   - Set card `injury_tier`, `injury_started_at`, compute `injury_recovery_days` using  
     `ceil(base_days / (1 + 0.2 * hospital_level))` for admit path; untreated uses multiplier as if level 0 (1.0×) for day countdown.
   - If bed free: INSERT `hospital_patients`, set `in_hospital=true`, `expected_recovery_date = now() + recovery_days`; append to `admitted`.
   - Else: `in_hospital=false`; append to `overflow`.
4. Return `{ "admitted": [...], "overflow": [...] }`.

**Security**: SECURITY DEFINER; validate cards owned by `p_owner_id`.

## Bot follow-up

| Result | UX |
|--------|-----|
| admitted only | Optional summary line in match footer / ephemeral |
| overflow non-empty | DM select: discharge patient OR leave untreated; on DM fail → Hospital panel waiting list |

## Daily recovery (injury portion)

- Discharge rows where `expected_recovery_date <= now()` and `discharge_date IS NULL`; clear card injury fields; `in_hospital=false`.
- Untreated: decrement `injury_recovery_days`; clear injury when ≤ 0.

## Idempotency

Prefer passing `p_match_history_id` (optional in v1) to ignore duplicate post-match calls for the same match; if omitted, tasks should still avoid double-calling from reward recovery paths.
