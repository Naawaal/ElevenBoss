# Research: Contract & Wage System (019)

**Date**: 2026-07-14  
**Purpose**: Pre-integration assessment — audit ElevenBoss wages/contracts, study FCM peers, PM/user lens, design blueprint for Speckit plan.

---

## 1. Audit — Current ElevenBoss implementation

### What exists today

| Piece | State |
|-------|--------|
| `calculate_weekly_wages` (package) | Formula `(max(OVR,40) - 40)² × wage_scale_factor(1.2) + 10` — **forecast only**; Finances passes **starting XI** cards |
| `/profile` Finances embed | `Estimated weekly wages … *(not auto-deducted)*` (`economy_cog.py`) |
| `contract_expires_at` on cards | Display + renew; **no hard gameplay teeth** on expiry |
| `renew_contract` RPC | Coins via economy pipe; extends expiry; blocks age ≥35 |
| Weekly/Monday schedulers | Aging, academy, etc. — **no payroll job** |
| `senior_roster_cap` (e.g. 48) | Hard squad size pressure, independent of wages |
| Club `coins` | All mutations via `apply_club_economy` (must stay) |

### What does **not** exist

- Automatic weekly wage deduction  
- Debt / unpaid strike state  
- Expiry → free agent / barred from XI  
- Wage columns that diverge from formula (if wage is derived each week from OVR, may not need stored wage — plan must choose stored vs derived)

### Squad size vs wages

- Soft/hard **roster cap** already discourages infinite hoarding.  
- Wages should **amplify** trading pressure, not replace the cap.  
- Academy / listed / injured inclusion must be explicit or bills will surprise.

---

## 2. Competitive research (FCM peers)

### EA Sports FC 26 Career Mode

- Weekly wages; budgets and board expectations.  
- Contracts by years; renewals with wage demands.  
- Unhappy players if wages unpaid / role issues (morale).  
- Scale: OVR + reputation + age drive wage expectations.

**Takeaways**: Weekly cadence; morale as soft stick; renewals as negotiation (ElevenBoss can simplify to fixed formula cost).

### Football Manager

- Detailed wage structures, clauses, non-playing wages.  
- Cash flow critical; debt → board intervention / fire-sale.  
- Too heavy for Discord slash UX.

**Takeaways**: Steal **ideas** (cashflow, consequence ladder), not UI complexity.

### Top Eleven

- Season-linked contracts; renewals; financial fair-ish pressure.  
- Failure to manage finances can force **sales** — often felt as harsh on casuals.  
- Wage bill visible and central to club management identity.

**Takeaways**: Visibility + season/week rhythm; soften auto-sell into warnings + optional force-list of low-value cards only if needed later.

### Cross-game patterns

| Pattern | Peer use | ElevenBoss fit |
|---------|----------|----------------|
| Weekly payroll | Almost universal | Align Monday UTC job |
| Scale by OVR | Universal | Extend existing formula |
| Age premium / decline | FM/FUT career | Factor into formula |
| Can’t pay → debt | FM / TE | Soft debt + strikes for Discord |
| Expiry → leave | Universal | Grace then block/release |
| Encourage trading | Caps + wages | Wages + existing roster cap |

---

## 3. User & PM perspective

### Manager wants

- Feel that big squads **cost** something.  
- Forecast that matches what gets charged.  
- Renew prompts before a star walks.  
- Recovery path after a bad week (friendries/login/store), not instant wipe.

### Manager hates

- Surprise 0-balance after offline weekend.  
- Losing best player with no DM/ephemeral warning.  
- Chores: renew 48 cards individually every week without bulk UX.

### PM wants

| Goal | Design choice |
|------|----------------|
| Economy sink | Payroll via `apply_club_economy` |
| Don’t break coin faucet math | Bill ≈ fraction of weekly match+login income; config-tunable |
| Division fairness | Optional multiplier by intensity/division later |
| Anti-hoard | XI-or-senior wages + roster cap |
| Casual safety | Flag + first-week grace + soft unpaid tiers |

---

## 4. Design blueprint (for `/speckit.plan`)

### Wage calculation

- Baseline: existing `calculate_weekly_wages` inputs.  
- Extend factors: **OVR, rarity, age, potential** (weights in config).  
- Decide **scope**:  
  - **Recommended v1**: Starting XI only (or XI + bench), *or* all senior non-academy — freeze one in plan.  
- Store vs derive: derive at payroll time from current OVR (simpler; no stale wage column) unless UI needs pinned “agreed wage.”

### Payment schedule

- Weekly job (Monday UTC, with aging).  
- Idempotent payroll run key per club per week.  
- Ledger reason e.g. `weekly_payroll`.

### Non-payment consequences (ladder)

Suggested Discord-casual ladder (resolve in plan):

1. **Partial pay + debt counter** (coins → 0, remainder debt).  
2. **Strike N**: morale/match intensity penalty or blocked non-league friendlies.  
3. **Strike N+**: cannot register new marketplace listings / scouting until debt cleared.  
4. **Last resort (P3)**: auto-list lowest-value reserve (not star XI) — only if needed.

Avoid day-1 FM liquidation.

### Contract renewals

- Keep `renew_contract` cost model; surface reminders on Finances + profile.  
- **Grace** after `contract_expires_at` (e.g. 7 days): reminder, still playable.  
- **Past grace**: cannot start in XI; optional free release to regen/agent after second window.  
- Age ≥35: keep no renew (retirement path).

### UI/UX

- `/profile` Finances: **forecast + last payroll + next run + debt**.  
- `/player-profile`: contract timer + Renew.  
- Optional `/development` or Finances soft banner when strikes &gt; 0 — no new slash.

### Database / backend

| Piece | Purpose |
|-------|---------|
| `game_config` flag `wages_payroll_enabled` | Default false |
| `payroll_runs` or ledger-only idempotency | Prevent double bill |
| Optional `players.payroll_debt` / strikes | Consequence state |
| Extend renew + expiry gates in squad/match | Teeth |
| Scheduler job `process_weekly_payroll` | Club loop via RPC batch |

### Migration path

1. Backfill null expiries to **now + N months**.  
2. No coin wipe on enable.  
3. Flag off → forecast only (current truth).  
4. Soft enable: grace week with **50% bill** or alert-only dry run in ops.  
5. Bot/AI clubs: exempt or micro-bill via config.

---

## 5. Frozen decisions (resolved in plan.md)

| ID | Topic | Decision |
|----|-------|----------|
| D1 | Wage scope v1 | **Starting XI only** (matches Finances today) |
| D2 | Stored wage | **Derive** — no per-card wage column |
| D3 | Formula | Keep OVR base; rarity/age/POT multipliers config-tunable (age/POT off by default) |
| D4 | Flag | `wages_payroll_enabled` default **false**; `wages_payroll_bill_scale` for soft launch |
| D5 | Unpaid | Debt + strikes; partial pay; **no auto-sell** |
| D6 | Strike ladder | ≥2 friendlies; ≥3 P2P/scout — **RPC-enforced**; agent OK |
| D7 | Renew | Keep 7-day default via `contract_renewal_days`; age ≥35 block |
| D8 | Expiry | 7-day grace → **block XI assign + match**; no auto-release in v1 |
| D9 | AI clubs | **Exempt** (`is_ai`) |
| D10–D14 | Ops | Idempotent `payroll_runs`; Monday 00:05 UTC; migration **063**; next-week bill only; null expiry backfill +30d |
| D15 | Morale | **No** unpaid morale mutation |

See [plan.md](./plan.md) for full freeze table.


---


## 6. References (code anchors)

- `packages/economy/economy/engine.py` — `calculate_weekly_wages`  
- `apps/discord_bot/cogs/economy_cog.py` — Finances embed  
- `renew_contract` RPC + profile renew UI  
- Schedulers in bot `main` / jobs for Monday cadence  
- Economy pipe: `apply_club_economy` / `economy_rpc`
