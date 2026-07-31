# Contract: Progression Effective Potential

**Feature**: `049-rarity-potential-integrity`  
**Integrity**: **US-42.2**  
**RPCs / helpers**: `allocate_skill_point`, `process_stat_drill`, `claim_evolution_reward`, `process_daily_academy_growth`, `train_with_fodder` (and any other path that gates on POT), mentor eligibility checks

## Effective potential

```text
effective_pot = LEAST(stored_potential, rarity_potential_cap(rarity))
```

All “at potential” / “would exceed potential” checks MUST use `effective_pot`, not raw stored POT, until and after historical repair (defense in depth).

## Dynamic match POT writer

`process_match_result` (and Python `apply_dynamic_potential_boost`) MUST also SELECT/pass `rarity` and compute:

```text
new_pot = LEAST(rarity_cap, current_pot + boost, base_pot + 10)
```

Youth eligibility rules unchanged.

## Mentor

- Do not reverse historical mentor transfers as part of POT repair.
- Before `transfer_mentor_xp`, both source and target MUST satisfy the rarity potential invariant (or effective-pot safe state).

## Drill soft-fail

Preserve existing soft-fail for drill **stat** boost when at cap; XP/costs still apply. Cap check uses `effective_pot`.
