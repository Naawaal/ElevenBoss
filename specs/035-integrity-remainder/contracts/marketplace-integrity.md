# Contract: Marketplace Integrity (US-42.6)

## Normative

| Rule | Enforcement |
|------|-------------|
| One buyer wins | `purchase_transfer_listing` row lock + `active` check |
| Own-buy forbidden | RPC raise |
| Tax burn | Buyer debit − seller net; registry documents sink |
| List while busy / MatchLocked | `assert_card_action_allowed` + `assert_not_in_match` |
| Cancel / expire once | Status terminal; re-run no-ops |
| Buy-it-now only | No bidding (`017`) |

## Acceptance greps / tests

- Race suite or smoke (`tests/test_transfer_market_race.py` or equivalent)
- Source: own-buy check present in purchase RPC
- List create calls card assert

## Non-goals

- Rewrite transfer UX; change tax %; bidding
