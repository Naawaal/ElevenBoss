# Contract: Repair & Reimbursement

**Feature**: `049-rarity-potential-integrity`  
**Integrity**: **US-42.7** / **US-42.9**  
**Tools**: `scripts/potential_cap_audit.py` (dry-run), `scripts/potential_cap_repair.py` (mutate)

## Non-negotiable gate

No production mutation of cards or balances until:

1. Read-only anomaly inventory complete  
2. Dry-run reimbursement report produced for **every** affected card  
3. Each card has `refund_confidence` ∈ {`EXACT`,`RECONSTRUCTED`,`MANUAL_REVIEW`,`NONE`}  
4. Unclassified count = 0  
5. Material `MANUAL_REVIEW` cases have an explicit human policy (or remain skipped)

## Categories

| Cat | Repair | Auto refund |
|-----|--------|-------------|
| A | Cap POT/base only | None (`NONE`) |
| B | Cap + attribute normalize + true OVR | Removed paid progression |
| C | Normalize illegal generated baseline | Subsequent paid removed only |

## Refund principle

Refund resources attached to progression **actually removed**. Never refund solely for `old_POT − new_POT`. Never invent fusion/item refunds without evidence. Never algorithmic marketplace damages.

## Pipes

- Coins / action energy → `apply_club_economy` with idempotency keys  
  `potential_cap_fix:<batch>:<card>:coins|energy|…`  
- SP → atomic update keeping `skill_points` / `skill_points_spent` consistent  
- Idempotency: second run → 0 extra refunds (audit `UNIQUE(batch_id, card_id)`)

## Attribution

- Card correction → current card  
- Resource refund → paying manager when reconstructable; else `MANUAL_REVIEW`  
- Do not reopen evolutions after refunding rewards  

## Notification order

```text
snapshot → repair → verify → refund → verify → (constraints) → DM
```

DM only after repair+refund success. DM failure does not roll back repair. Copy distinguishes “resources returned” vs “none required” (POT-only).

## Confidence honesty

Dry-run MUST surface that drill ledger metadata can be **EXACT** while skill allocation may only have aggregate `skill_points_spent` (**RECONSTRUCTED** / **MANUAL_REVIEW**) — never falsely precise refunds.
