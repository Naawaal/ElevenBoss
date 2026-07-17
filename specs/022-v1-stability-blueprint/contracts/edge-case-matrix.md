# Contract: Recent-Feature Edge Matrix (E1–E12)

**Feature**: `022-v1-stability-blueprint`  
**Maps to**: Spec E1–E12, User Story 6, SC-008

For each edge: run the **Probe**, record **Verdict** (Proven / Disproven / Intentional), and only open a fix ticket for **Proven** at High+ severity.

| ID | Probe | Expected if healthy |
|----|-------|---------------------|
| E1 Mentor ceiling | Mentor when youth near XP soft-cap / mentor at exact remaining headroom | No SP burn without matching youth XP grant; clear error if blocked |
| E2 Mentor conflicts | Mentor while evo-active / transfer-listed / hospital | Block with reason **or** documented allow — UI and RPC agree |
| E3 Hospital loop | Rapid discharge → admit cycles | No fatigue exploit beyond published recovery rules |
| E4 List flip | List → cancel → re-list around tax/cooldown | Cooldown / rules hold; no tax-free flip loophole beyond design |
| E5 Roster race | Buy while buyer at senior cap; or promote then buy | Exactly one path succeeds; no over-cap roster |
| E6 Wage shrink | Change XI inside Monday payroll window | Bill consistent with lock/FOR UPDATE semantics; no free unpaid gap |
| E7 Strike≥3 | With ≥3 strikes: listing/scout blocked; agent sale allowed | Matches wage ladder; if so → Intentional |
| E8 Double sim | Dynamics season + interval auto-sim job | Interval skips dynamics; midnight tick owns |
| E9 Pause mid-reg | Pause during open registration | No orphan duplicate registration seasons next cycle |
| E10 Force End + reopen | Force End then expect Monday rule | Reopen follows Monday / documented rule — not same-day surprise |
| E11 Evo cancel | Cancel evo then match tick / cooldown farm | Soft-lock and cooldown behave as published; no reward farm |
| E12 Retro + P2P | Pending rewards on card sold to new owner | New owner claims; old owner cannot |

## Recording

Append Verdict + date + evidence (test name / Discord note) into `spec.md` registry Notes for each E*.

## Exit

SC-008: all twelve Verdict set; every Proven High+ Closed before declaring v1 stable.
