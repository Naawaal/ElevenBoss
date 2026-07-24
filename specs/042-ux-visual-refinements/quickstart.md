# Quickstart: Store / Swap / Hospital UX Refinements

**Feature**: `042-ux-visual-refinements` | **Date**: 2026-07-23

Manual + unit validation after implementation. No migrations to apply.

## Prerequisites

- Bot running against a registered test club.
- Repo assets present: `assets/admited.png`, `assets/fonts/Roboto-*.ttf`.
- Contracts: [energy-near-full-guard](./contracts/energy-near-full-guard.md), [swap-compare-visual](./contracts/swap-compare-visual.md), [hospital-admitted-visual](./contracts/hospital-admitted-visual.md).

## Unit checks

```bash
pytest tests/test_energy_near_full.py tests/test_hospital_board_slots.py tests/test_squad_swap_confirm.py -q
```

Expected: all pass (near-full matrix, slot cap/empty, Confirm gate unchanged).

## Manual — Store (P1)

1. Set test club energy near max (e.g. `action_energy = max_energy` or `max_energy - 3` via ops/SQL).
2. Run `/store`.
3. **Expect**: Buy Energy Refill greyed out; label `Energy already full` or `Near maximum`; embed explains unavailability; other buttons work.
4. Spend energy (match/drill/refill elsewhere) until clearly below threshold; reopen `/store`.
5. **Expect**: Buy Energy Refill enabled; purchase still costs tier coins and adds energy.

## Manual — Swap (P2)

1. `/squad` → Swap Players with ≥1 healthy compatible reserve.
2. **Expect**: Compare image with OUT/IN placeholders; selects present; Confirm off.
3. Select starter then reserve.
4. **Expect**: Image updates to both players (name/pos/OVR visible); Confirm on; confirm swap succeeds as today.
5. Empty-bench or incompatible-only club: Confirm stays off; no fake IN player on image.

## Manual — Hospital (P3)

1. `/profile` → Manage Hospital with **zero** admitted.
2. **Expect**: Clipboard board image (empty rows) + “*No one admitted.*”; waiting list still shown if any.
3. Admit a patient; panel refreshes.
4. **Expect**: Name appears on board row; embed patient line still has ETA.
5. Discharge; reopen/refresh.
6. **Expect**: Name gone; no stale overlay.
7. (Optional) Temporarily rename `assets/admited.png` aside and reopen → text-only panel still usable.

## Done criteria

- SC-001–SC-007 from [spec.md](./spec.md) satisfied for the three surfaces.
- `change_log.md` updated with a short player-facing note when shipping.
