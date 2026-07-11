# Contract: Fatigue in matches (Phase 1)

## Scope

Competitive matches only: **bot** and **league**. Friendlies: no drain, no bench recovery, no penalty hydration required (cards may still carry fatigue from prior competitive play — sim may apply penalties if hydrated; prefer **not** applying competitive fatigue effects in friendlies for sandbox purity: load fatigue but skip post-match writes).

## Pre-match hydration

`card_from_db_row` / match card builder MUST set:

| Field | Source |
|-------|--------|
| `fatigue` | `player_cards.fatigue` (default 100) |
| `phy` | existing |
| card `id` | existing |

Injured starters MUST be blocked before match start (Phase 2 gate); Phase 1 may allow play while only fatigued.

## In-sim penalty (NSS)

`phase_stat_value` applies fatigue multiplier to the **phase attribute** mean **before** `0.7 * zone_ovr + 0.3 * phase_attr`.

| Fatigue | PAC | DRI | PAS | DEF | SHO |
|---------|-----|-----|-----|-----|-----|
| 75–100 | 0% | 0% | 0% | 0% | 0% |
| 50–74 | −8% | −5% | −3% | 0% | −3% |
| 25–49 | −20% | −15% | −10% | −5% | −10% |
| 1–24 | −45% | −30% | −20% | −15% | −25% |
| 0 | −60% | −40% | −30% | −25% | −35% |

Map phase attrs: PAC→pac, DRI→dri, PAS→pas, DEF→def, SHO→sho (and overall/MIDFIELD uses overall with no extra attr penalty beyond blend inputs as implemented).

Pure helper: `fatigue_stat_multiplier(fatigue, stat_key) -> float` in `packages/player_engine/fatigue.py` (or match_engine importing player_engine — prefer player_engine to keep formulas centralized).

## Post-match: `apply_match_fatigue`

**Caller**: `apply_bot_match_rewards` / `apply_league_human_rewards` (after economy + XP success path; if XP soft-zeros OK still apply fatigue).

**Input (conceptual)**:

| Arg | Meaning |
|-----|---------|
| `p_owner_id` | club discord id |
| `p_starter_drains` | jsonb `{card_id: drain_int}` computed in Python via drain formula |
| `p_bench_ids` | uuid[] — owned reserves that sat the match (not in XI) |

**Drain formula** (Python, then persist):

```text
drain = round(base_drain - phy * 0.15 + tactic_mod + intensity_mod)
base_drain = 22 (game_config)
tactic_mod = +8 Attack / −4 Defend / 0 Neutral (home touchline stance for human club)
intensity_mod = +5 if opponent global LP tier is 2+ higher (else 0)
result fatigue = max(0, fatigue - drain) for starters
bench: min(100, fatigue + fatigue_bench_per_match)  # default 15
```

**Bot clubs / auto-sim**: still apply drains to human club’s cards; bot-owned cards if any follow same rules when they have card rows.

**Success**: batch UPDATE; no per-card round-trips from app.

**Must not**: touch `action_energy` or coins.

## Daily recovery (fatigue portion)

`process_daily_recovery`: `fatigue = LEAST(100, fatigue + CASE WHEN in_hospital THEN 45 ELSE 20 END)` for cards with fatigue &lt; 100.
