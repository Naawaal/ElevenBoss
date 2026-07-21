# Contract: Lifecycle Transitions

**Feature**: `026-league-lifecycle-rulebook`  
**Consumer**: `LeagueLifecycleEngine.process_due_transitions(now)` and admin shared transition API

## Authority

Competitive state changes ONLY through named transitions below. The scheduler MUST NOT embed alternate rules.

## Season transitions

| From | To | Trigger | Guards | Side effects (once) |
|------|-----|---------|--------|---------------------|
| dormant / idle | registration_open | `next_registration_at <= now` or admin | cutover effective XOR legacy path; no other open season; announce channel resolvable for auto-open | Create season row; registration deadline; outbox `registration_open` |
| registration_open | registration_locked | deadline or admin | season still open | Lock registrations; op `season:{id}:registration_close` |
| registration_locked | preparing | humans >= min | deposits chargeable | Op `season:{id}:prepare`; charge deposits; seat divisions; bots; fixtures; matchdays; freeze TZ windows |
| registration_locked | cancelled | humans < min | — | Refund if charged; schedule next registration; outbox under-min |
| preparing | active | prepare succeeded | all matchdays have UTC windows | Op `season:{id}:activate`; outbox fixture release |
| preparing | failed | infra error | retryable | Journal failure; allow re-prepare |
| active | paused | admin / guild unreachable | — | Record `pause_started_at` |
| paused | active | admin resume | — | Rebase unresolved matchday/fixture windows by paused duration |
| active | settling | all matchdays completed | every fixture terminal | Op `season:{id}:settle` start |
| settling | completed | rewards + promo committed | finals written | Ops rewards/promotion; outbox ceremony; set offseason end |
| * | cancelled | admin force-end | — | Cancellation settlement; normally no full prizes/promo unless completion threshold met |
| completed | registration_open | offseason end | cutover still on | Next cycle |

## Operation keys (normative)

```text
season:{season_id}:registration_close
season:{season_id}:prepare
season:{season_id}:activate
matchday:{matchday_id}:open
matchday:{matchday_id}:remind
matchday:{matchday_id}:lock
matchday:{matchday_id}:complete
fixture:{fixture_id}:resolve
fixture:{fixture_id}:settle
season:{season_id}:settle
season:{season_id}:promotion
season:{season_id}:rewards
season:{season_id}:next_registration
```

## Exactly-once test

```text
for _ in range(100):
    engine.process_due_transitions(fixed_now)
assert each operation_key succeeded at most once
assert each fixture has one terminal result
assert rewards paid once
assert promotion applied once
```

## Admin parity

Admin Start / Close Registration / Settle MUST call the same transition handlers as automation (same operation keys).
