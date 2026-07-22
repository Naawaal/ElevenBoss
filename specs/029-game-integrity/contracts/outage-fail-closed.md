# Contract: Outage Fail-Closed Posture (US4)

**Parent**: [../spec.md](../spec.md) | **Children**: 42.4 match, 42.5 league (`026`/`027` overlay), 42.8 jobs

| Scenario | Expected | Reasoning | Recovery pointer |
|----------|----------|-----------|------------------|
| Discord API down mid-action | Mutation may complete; presentation retries; no second grant | UI is presentation-only | 42.4 present-retry; hub re-open |
| Top.gg down | Pack/vote claim **denied** | Fail closed — no free pack | Store copy; retry when dependency healthy |
| Render / bot restart | In-flight match: settle-once or abandon per classifier; locks reconcile on boot | No double reward | `033` / `match_recovery`; mig `077` |
| Guild remove / re-add | Club identity preserved; soft unlink; no delete | INV-01 ownership | `030` identity |
| Scheduler miss (deadline) | Catch-up settle **once**; **no sporting forfeit invented from infra** | Absence ≠ outage forfeit | `034` + `026`/`027`; job catalog `035` |

## Operator quiz (Validation E)

1. Top.gg down — free pack or deny? → **Deny**  
2. Embed fails after settle — re-grant coins? → **No; retry present only**  
3. Bot offline past league deadline — auto-forfeit teams? → **No**  
4. Restart during rewarded match — pay again? → **No; complete-if-rewarded / settle-once**  
5. Who owns exhaustive edge catalog? → **US-42.10 / `035`**
