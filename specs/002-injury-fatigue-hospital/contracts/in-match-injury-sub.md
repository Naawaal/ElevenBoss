# Contract: In-Match Injury Substitution (Phase 3)

## Scope

| Match type | Interactive UI? | Injury authority |
|------------|-----------------|------------------|
| Bot battle (human) | Yes | Mid-match A+C → persist recorded |
| League human (live) | Yes (injured side only) | Same |
| League auto-sim / silent | No — auto-resolve | Same |
| AI club | No — auto-resolve | Same |
| Friendly | No injury | Unchanged sandbox |

## Event payload (yielded to Discord)

```text
type: "INJURY" | "INJURY_STOPPAGE"   # prefer INJURY with interactive=true for compat
minute: int                         # < 90 for prompts
interactive: bool                   # false if auto-resolved already / 90+
side: "home" | "away"
injured_card_id: str | None
injured_name: str
injury_tier: 1|2|3
subs_remaining: int                 # 0..3
bench: list[{card_id, name, position, overall, fatigue}]  # sorted fatigue desc, then OVR
options: ["sub", "play_on"] | ["play_on"] | []   # empty → 10-men auto
gk_emergency: bool
```

## Discord consumer algorithm

```text
async for ev in stream_match(...):
  if ev is interactive injury for this human owner:
    post InjurySubView (Select bench + Play On button)
    wait asyncio.wait_for(event.wait(), timeout=30)
    on timeout: auto_pick_or_ten_men(...)
    write resolution onto MatchState / runtime sidecar
    # do NOT call next(event) / asend — just continue loop
  render commentary as today
```

View rules:
- `interaction_check`: only injured side’s manager
- Timeout disables components; match loop proceeds
- Non-persistent view (match-scoped); no `bot.add_view` required

## MatchState / runtime fields

| Field | Role |
|-------|------|
| `bench_home` / `bench_away` | `list[MatchPlayerCard]` at kickoff |
| `subs_used_home` / `subs_used_away` | int, max 3 |
| `pending_injuries` | queue of pending InjuryPending |
| `recorded_injuries` | list for post-match RPC |
| `compromised_card_ids` | set/list for Play On ×0.50 |
| `sub_resolution` | latest SubResolution written by UI/auto |
| `sub_wait_event` | `asyncio.Event` (sidecar, not Pydantic field) |

## Pure resolve API (`substitution_resolve.py`)

```text
auto_pick_bench(bench, injured_position) -> MatchPlayerCard | None
apply_sub(squad, bench, injured_id, replacement_id) -> (squad, bench)
apply_ten_men(squad, injured_id) -> squad
emergency_gk_card(outfield) -> card with gk penalty flag
play_on_tier_upgrade(tier, rng) -> tier  # +60% chance +1, cap 3
```

## Post-match persistence

```text
apply_post_match_fitness(..., recorded_injuries=[...], skip_roll=True)
  → process_post_match_injuries(p_injuries=recorded)
  → still apply fatigue drains as Phase 1
```

If `recorded_injuries` empty and Phase 3 path not used → keep Phase 2 roll (compat).

## Edge matrix

| Case | Behavior |
|------|----------|
| Subs remaining + bench | Prompt; timeout auto-pick |
| Subs remaining + empty bench | 10-men; no prompt (or info-only) |
| Subs used up | 10-men / Play On auto; no Select |
| GK + GK on bench | Auto-sub GK (optional skip wait) |
| GK + no GK bench | Emergency GK prompt or auto outfield |
| Two injuries same phase | Sequential prompts |
| minute ≥ 90 | Record only; no prompt |
| Play On | Stay on pitch; ×0.50; tier upgrade risk at persist |
