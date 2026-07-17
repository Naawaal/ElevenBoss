# Data Model: v1 Stability Blueprint

**Feature**: `022-v1-stability-blueprint` | **Date**: 2026-07-15

This feature does **not** introduce new Postgres tables in the happy path. The “data model” is the **Issue Registry** and its status lifecycle, plus references to existing domain entities touched by remediations.

## Registry entities (documentation)

### Issue

| Field | Description |
|-------|-------------|
| `id` | Stable ID (`C1`, `H1`, `M5`, `L2`, `E8`, …) |
| `severity` | Critical / High / Medium / Low |
| `module` | Match Engine, Economy, Training, Evolution, League, UI/UX, Database, Ops, … |
| `symptom` | What managers / ops observe |
| `expected` | Correct behavior after fix or intentional design |
| `status` | See state machine below |
| `bundle` | Remediation bundle id (`B-Transfer`, …) or empty |
| `wave` | Target wave 0–4 |
| `notes` | Repro, disposition counts, links to tests |

### EdgeCase (E*)

Same as Issue, plus `verdict`: Proven / Disproven / Intentional once Wave 3 completes.

### RemediationWave

| Field | Description |
|-------|-------------|
| `number` | 0–4 |
| `focus` | Verify / Money / Truth / UX / Polish |
| `exit_gate` | Mapped Success Criteria IDs |

### Bundle

Groups issues that should land in one PR or sequential commits: `B-Transfer`, `B-Wages`, `B-League-Tick`, `B-Automation`, `B-OVR`, `B-Match-Parity`, `B-Match-Stale`, `B-Evo-Truth`, `B-Retro`, `B-UI-Select`, `B-Mentor`, `B-Hospital`, `B-Copy`, `B-Hygiene`, `B-Audit`, `B-Schema`.

## Status state machine

```text
Open ──────────► In Progress ──► Closed
  ▲                    │
  │                    │ (fix shipped + check exists)
Verify ──(pass)───────┴──► Closed
  │
  └──(fail)──► Open

Suspect ──(prove)──► Open
        └──(disprove / intentional)──► Closed (Intentional)

Intentional ──► Closed (no code)   # label only
```

**Rules**:
- Never delete IDs; reclassify status only.
- Closed Critical/High must name an automated test or smoke step in Notes.
- Intentional items are not “fixed” into new features without a new Spec Kit feature.

## Existing domain entities (touch points)

| Entity | Stability relevance |
|--------|---------------------|
| `players` (coins, debt, strikes, energy) | Money pipe regressions; payroll |
| `player_cards` (overall, potential, owner_id, stats) | OVR truth; ownership after P2P; retro claim |
| `transfer_listings` / sales log | Race purchase; expiry |
| `payroll_runs` | Idempotent weekly payroll |
| `league_matchday_manager_awards` | MoMD once-per-MD |
| `league_seasons` + fixtures | Double-sim / automation |
| `pending_level_rewards` | Owner claim after transfer |
| `mentor_transfer_log` | Daily mentor cap |
| Hub Discord Views (ephemeral) | Select empty-state |

## Conditional schema (only if reopen)

If Wave 0–1 requires a forward fix:

| Possible object | When |
|-----------------|------|
| New uniqueness / guard in existing RPC | Broken idempotency proven |
| `066_*.sql` + verify_required_schema entries | Columns/functions bots newly depend on |

Do **not** invent a `stability_issues` table.
