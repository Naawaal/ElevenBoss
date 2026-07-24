# Contract: Energy Near-Full Store Guard

**Feature**: `042-ux-visual-refinements` | **Surface**: `/store` Club Store hub

## Pure API (`packages/energy`)

```text
is_energy_near_full(current: int, maximum: int) -> bool
near_full_reason(current: int, maximum: int) -> "full" | "near" | None
```

| Input | Output |
|-------|--------|
| `maximum <= 0` | `False` / `None` (fail-open) |
| `current >= maximum` | `True` / `"full"` |
| `current >= ceil(0.95 * maximum)` or `current >= maximum - 5` | `True` / `"near"` (if not full) |
| else | `False` / `None` |

When both 95% and within-5 would apply but `current < maximum`, reason is `"near"`. Full takes precedence at/above max.

## Discord UI contract

| State | Button `store_energy_refill` | Label (suggested) | Embed Energy Refill field |
|-------|------------------------------|-------------------|---------------------------|
| `reason is None` | enabled | `⚡ Buy Energy Refill` | Existing price copy |
| `full` | disabled | `⚡ Energy already full` | Note: energy at maximum — refill unavailable |
| `near` | disabled | `⚡ Near maximum` | Note: energy near cap — refill unavailable |

- Recompute on every `show_store` (including post-purchase / post-login refresh).
- Other store buttons unaffected.
- No RPC signature change; disabled control must not invoke `purchase_energy_refill`.

## Non-goals

- Changing refill grant (+50), costs, or daily tier caps.
- Changing `max_energy` defaults.
