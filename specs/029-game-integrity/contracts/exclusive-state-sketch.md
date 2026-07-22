# Contract: Exclusive-State Sketch (INV-03 / INV-17)

**SoT**: [../spec.md](../spec.md) §§5–6. Deep matrices: US-42.2 (`031`), US-42.3 (`032`).

## Player card (exclusive busy)

Typical exclusive / blocking overlays: **Listed**, **Hospital**, **Evolving**, **MatchLocked**, **InAcademy**, **Retired**.

Default: conflicting mutations **Block** (fail closed). Narrow allow-lists only in Locked child specs.

### Conflict decision matrix (epic §6.2)

| Action vs state | Listed | Hospital | Evolving | MatchLocked | Retired |
|-----------------|--------|----------|----------|-------------|---------|
| Start match (include) | Block | Block | Block* | Block | Block |
| Drill / fusion / allocate | Block | Block | Block* | Block | Block |
| List transfer | — | Block | Block | Block | Block |
| Agent sell | Block | Block | Block | Block | Block |
| Buy as target | — | — | — | — | Block |

\*Unless child defines a narrow allowed sub-action. Default = Block.

## Club (soft lifecycle)

**Active / Inactive / Abandoned** (US-42.3): league join and similar competitive actions gate on club eligibility — not a second economy.

## Appendix — Transfer list dry-run (`017`)

Against this sketch + `017` list eligibility:

| Overlap | Epic expectation | Notes for 42.2 |
|---------|------------------|----------------|
| List while MatchLocked | Block | Enforced via match lock + `assert_card_action_allowed` |
| List while Hospital | Block | State machine |
| List while Evolving | Block | State machine |
| List while in starting XI | Domain rule (017 may allow or block) | Document in 42.2/42.6 if XI is exclusive vs soft |
| Buy while Listed on another listing | One ownership; seller listing cancel rules | INV-02/13 |

Undocumented soft overlap called out for children: **XI roster membership** is not always an exclusive state name in the epic matrix — 42.2/42.6 must keep list-from-XI behavior explicit and fail-closed where competitive integrity requires it.
