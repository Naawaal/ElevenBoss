# Contract: Finances UI & strike surfaces

**Feature**: 019 | **Surface**: `/profile` → Finances (`economy_cog`) — no new slash

## Flag off (`wages_payroll_enabled = false`)

Keep today’s promise:

- Show **Estimated weekly wages** for Starting XI  
- Copy includes **`(not auto-deducted)`**  
- Do not show debt/strikes as live obligations (or show debt only if somehow non-zero from a prior enable — prefer hide)

## Flag on

Embed fields (minimum) — Finances SELECT must include:

| Field | Content |
|-------|---------|
| Weekly wage bill | Derived XI total × scale (same number payroll uses) |
| Paying players | Count of XI cards in bill |
| Club debt | `payroll_debt` |
| Strikes | `payroll_strikes` + short ladder hint |
| Last payroll | `last_payroll_at` / week_key + paid amount from latest `payroll_runs` |
| Next payroll | “Monday 00:05 UTC” (or next Monday) |
| Contract alerts | Count of XI cards in grace / past grace |

Remove or replace “not auto-deducted” with **“Deducted every Monday UTC”**.

## Strike enforcement

| Strikes | Bot UX | RPC (authoritative) |
|---------|--------|---------------------|
| ≥ `payroll_strike_friendly_block` (2) | Reject **friendly** match start | N/A if friendly is Discord-only; still block in bot |
| ≥ `payroll_strike_market_block` (3) | Pre-check list/scout flows | **Reject** in `create_transfer_listing`, `purchase_scouting_player`, `dispatch_youth_scout`, `sign_youth_scout_prospect` |
| any | — | **Agent sale** remains allowed |

Clear messaging: how to recover (play league/bot, claim login `/store`, reduce XI bill).

## Renew

- Unchanged entry: `/player-profile` Renew  
- Optional Finances button “Cards needing renew” — **YAGNI**: text list of names in embed is enough for v1
