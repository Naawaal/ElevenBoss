# Contract: Card Ingress Reject

**Feature**: `049-rarity-potential-integrity`  
**Integrity**: **US-42.9**  
**RPCs**: `register_new_player`, `claim_daily_pack`, `process_youth_intake`, `sign_youth_scout_prospect` (and any other JSON→`player_cards` insert)

## Rule

Before INSERT into `player_cards`, each card payload MUST be validated:

1. `rarity_potential_cap(rarity)` is not NULL  
2. `overall ≤ cap`  
3. `potential ≤ cap`  
4. `base_potential` is NULL or `≤ cap`  
5. `overall ≤ potential`

On failure: **reject** the operation (exception or envelope `rejected` — match existing RPC error style). Do **not** mutate POT upward to satisfy (5).

## Removed anti-pattern

```text
IF potential < overall THEN potential := overall   -- FORBIDDEN
```

## Python producers

Factory, regen, youth intake, gacha, support legendary, maintenance writers MUST call the same integrity validation before handing payloads to these RPCs. DB validation is defense in depth, not a substitute for correct generation.
