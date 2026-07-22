# Contract: Current Owner Ownership

**Feature**: US-42.1 | **INV-02, INV-14**

## Rules

1. Authoritative card owner = `player_cards.owner_id`.
2. Any stale denormalized `club_id` on reward rows is ignored for payee selection at claim time.
3. `claim_pending_level_rewards(p_owner_id)` credits only cards where `owner_id = p_owner_id`.
4. Card-scoped RPCs must re-check `owner_id` inside the transaction.
5. Coin balances belong to `players.discord_id`; economy pipe unchanged.

## Verification

| Check | Method |
|-------|--------|
| Claim filters current owner | Unit/SQL test or existing US-24 test extended |
| Transfer updates `owner_id` | Existing transfer tests remain green |
| Guard unregistered | `ensure_registered` |

## Non-goals

- Re-implementing transfer purchase (017 / US-42.6).
- Changing XP formulas.
