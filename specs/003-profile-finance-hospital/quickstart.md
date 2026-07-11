# Quickstart: Profile Finance & Hospital Hub

**Feature**: `003-profile-finance-hospital` | **Date**: 2026-07-11

Manual validation after implementation. Assumes migration `050` hospital schema is applied and Store hospital panel already works.

## Prerequisites

- Bot running against a DB with `players.hospital_level` and `hospital_patients`
- Test manager registered in a guild (command is guild-only)
- Optional: second card set for multi-patient truncation

## 1. Dashboard happy path

1. Ensure club has coins and `hospital_level >= 1` with 0–2 active patients (admit via Store hospital panel if needed).
2. Run `/profile`.
3. **Expect**: Finance section shows coins + gems; Hospital shows level, `occupied/capacity`, recovery multiplier, patient ETAs or “No injuries”; energy/division/record/trophies still present; three buttons visible.

## 2. Hospital not built

1. Use a club with `hospital_level = 0` (or temporarily test that state).
2. Run `/profile`.
3. **Expect**: Hospital empty-state copy directing to Store / build; no fake “full hospital” bed list.
4. Press **Manage Hospital**.
5. **Expect**: Hospital panel opens; upgrade path available; Back returns to refreshed `/profile`.

## 3. Manage Hospital round-trip

1. From `/profile`, open **Manage Hospital**.
2. Discharge or admit if options exist; or upgrade one level if affordable and off weekly cooldown.
3. Press Back to Profile.
4. **Expect**: Coins, level, beds, and patient list match the panel outcome ([profile-hospital-nav.md](./contracts/profile-hospital-nav.md)).

## 4. Finances + soft-deprecate

1. From `/profile`, press **Finances** — expect wallet + wages + facility levels; Back → profile.
2. Run `/club-finances` — expect same core content plus pointer to `/profile` ([club-finances-soft-deprecate.md](./contracts/club-finances-soft-deprecate.md)).

## 5. Club Stats

1. From `/profile`, press **View Club Stats**.
2. **Expect**: Squad hub (pitch + formation controls) on the same interaction flow.

## 6. Store path regression

1. `/store` → Club Facilities → Hospital Panel → Back to Facilities → Back to Store.
2. **Expect**: Unchanged navigation (origin defaults to facilities).

## 7. Edge checks

| Case | Expect |
|------|--------|
| Unregistered user | Registration guard message (no broken embed) |
| DM `/profile` | Discord guild-only rejection |
| Many patients | Truncated list + “Manage Hospital” cue |
| Stale buttons after timeout | Clear failure / re-run `/profile` |

## Automated checks

```bash
pytest tests/test_profile_hospital_summary.py -q
```

(Formatter/truncation/L0 copy unit tests — added during implement.)

## Related contracts

- [profile-dashboard.md](./contracts/profile-dashboard.md)
- [profile-hospital-nav.md](./contracts/profile-hospital-nav.md)
- [club-finances-soft-deprecate.md](./contracts/club-finances-soft-deprecate.md)
- [data-model.md](./data-model.md)
