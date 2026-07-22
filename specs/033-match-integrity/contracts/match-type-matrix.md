# Contract: Match Type Matrix

**Feature**: US-42.4

| Effect | Bot | League | Friendly |
|--------|-----|--------|----------|
| MatchLocked during live | Required | Required (both humans) | Required (both) |
| Economy coins/energy | Yes (keyed) | Yes (keyed) | No |
| Match XP + evo tick | Yes (once) | Yes (once) | No |
| Fixture binding | No | Yes | No |
| Restart mid-stream | Complete if paid else abandon | Resume/settle per fixture rules + abandon RPC | Abandon (no pay) |

Amend `spec.md` §B.3 before changing this table.
