# Contract: Child Spec Template (US-42.x)

**Parent**: [../spec.md](../spec.md)  
**Use**: Copy into each new Speckit feature created for US-42.1–US-42.10. Speckit `spec-template.md` sections remain mandatory; this contract adds integrity-required sections.

## Header (required)

```markdown
**Parent epic**: `specs/029-game-integrity` (US-42)
**Child ID**: US-42.N — <Title>
**Depends on**: <child IDs or "none">
**Overlays** (if any): <e.g. specs/026-..., specs/017-...>
**Status**: Draft | Locked
```

## Required extra sections

### A. Epic invariant touch list

List every INV-ID from the parent that this child **extends, enforces, or tests**. Do not silently weaken an INV.

### B. State machine / lifecycle (if domain has states)

**Child obligation (US-42.2 / US-42.3):** publish the full **action × state** matrix (not only the epic sketch). Cite [exclusive-state-sketch.md](./exclusive-state-sketch.md) as the starting Block defaults.

For each entity owned by this child:

- State list (must align with epic names or formally amend epic)
- Entry rules / exit rules
- Allowed actions table
- Blocked actions table
- Failure recovery (partial write, retry, outage)

### C. Logical actions & idempotency

| Action | Actor | Idempotency key pattern | Pipeline | Success | Reject reasons |
|--------|-------|-------------------------|----------|---------|----------------|
| … | … | … | Economy/XP/Ownership/Competitive | … | … |

### D. Source of truth

What is durable truth vs presentation for this domain? Cite parent SoT matrix.

### E. Outage & catch-up

What happens if Discord / bot / dependency is down mid-action? Fail closed vs settle-once.

### F. Implementation non-goals

Explicitly list what this child will **not** build (keep YAGNI).

### G. Acceptance tests (integrity)

Minimum:

- Double-invoke / replay
- Concurrent conflict (if applicable)
- Stale UI path
- At least one outage/restart path

## Naming short-names (suggested)

| Child | Suggested Speckit short-name |
|-------|------------------------------|
| US-42.1 | `identity-ownership` |
| US-42.2 | `player-state-machine` |
| US-42.3 | `club-state-machine` |
| US-42.4 | `match-integrity` |
| US-42.5 | `league-integrity` |
| US-42.6 | `marketplace-integrity` |
| US-42.7 | `economy-integrity` |
| US-42.8 | `scheduler-integrity` |
| US-42.9 | `rpc-invariants` |
| US-42.10 | `security-edge-catalog` |

## Amendment rule

If the child needs to change an epic principle or INV, stop: amend `specs/029-game-integrity/spec.md` first, then continue the child.
