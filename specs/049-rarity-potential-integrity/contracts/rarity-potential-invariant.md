# Contract: Rarity Potential Invariant

**Feature**: `049-rarity-potential-integrity`  
**Integrity**: **US-42.2** / **US-42.9**  
**Consumers**: All card generators, POT writers, persistence CHECKs, anomaly monitors

## Absolute caps

| Rarity | Max POT / max base POT | Max overall |
|--------|----------------------:|------------:|
| Common | 75 | 75 (via OVR ≤ POT ≤ cap) |
| Rare | 85 | 85 |
| Epic | 92 | 92 |
| Legendary | 99 | 99 |

## Always true

```text
overall ≤ potential ≤ rarity_cap(rarity)
base_potential ≤ rarity_cap(rarity)   -- when present
```

## Forbidden

- Raising `potential` to match an overall that exceeds rarity cap
- Dynamic boost past rarity cap (even if `base + 10` would allow it)
- Treating unknown rarity as Common
- Silent DB triggers that rewrite illegal values without failing the writer

## Mapping hosts

Exactly two implementations: Python `RARITY_POT_CAPS` / `rarity_potential_cap()`, SQL `public.rarity_potential_cap(text)`. Must stay parity-tested.
