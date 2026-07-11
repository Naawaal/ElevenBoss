# Research: Gacha Card Archetypes & Factory Reliability

**Feature**: `005-gacha-archetypes` | **Date**: 2026-07-11

## R1 — Persist archetype via existing `role` (RPC gap)

**Decision**: Use `player_cards.role` as the archetype label. Ship migration `051` so `register_new_player`, `claim_daily_pack`, `process_youth_intake`, `insert_scouting_pool_player`, and `purchase_scouting_player` read/write `role`. Add `scouting_pool_players.role TEXT DEFAULT 'Balanced'`.

**Rationale**: Spec FR-012 assumes role is the display home, and squad/`player_cog` already render `card.role`. Today every intake INSERT omits `role`, so Postgres always stores the column default `Balanced` — factory-only archetype labels would never reach managers. Extending jsonb payloads is the smallest fix (column already exists on `player_cards`).

**Alternatives considered**:
- Generation-only (no RPC change) — fails FR-012 / SC-003 (invisible identity after claim).
- New `archetype` column — YAGNI; duplicates `role`.
- Encode archetype in name/traits JSON — breaks existing Role Style UI.

## R2 — Archetype catalog (v1)

**Decision**: Three archetypes per position with roughly even roll weights (Complete/Balanced slightly favored at weight 40 vs 30/30 where noted). Weights below are **creation** distributions (must sum ≈ 1.0). True OVR still uses `engine.POSITION_WEIGHTS` (unchanged).

| Position | Archetype | Primary emphasis | Secondary / weak |
|----------|-----------|------------------|------------------|
| FWD | Poacher | sho 0.40, phy 0.20, dri 0.15 | pac 0.10, pas 0.10, def 0.05 |
| FWD | Speedster | pac 0.35, dri 0.30, sho 0.15 | pas 0.10, phy 0.05, def 0.05 |
| FWD | Complete Forward | existing FWD table (pac 0.20, sho 0.35, pas 0.10, dri 0.20, def 0.05, phy 0.10) | — |
| MID | Playmaker | pas 0.35, dri 0.25, sho 0.15 | pac 0.10, def 0.05, phy 0.10 |
| MID | Box-to-Box | pas 0.20, phy 0.20, dri 0.15, def 0.15, pac 0.15, sho 0.15 | balanced |
| MID | Destroyer | def 0.30, phy 0.25, pas 0.15 | dri 0.10, pac 0.10, sho 0.10 |
| DEF | Stopper | def 0.45, phy 0.30, pac 0.10 | pas 0.10, dri 0.03, sho 0.02 |
| DEF | Wing-Back | pac 0.25, pas 0.20, dri 0.15, def 0.25 | phy 0.12, sho 0.03 |
| DEF | Ball-Playing Defender | def 0.35, pas 0.25, phy 0.20 | pac 0.10, dri 0.07, sho 0.03 |
| GK | Shot Stopper | def 0.55, phy 0.25, pac 0.10 | pas 0.10, sho 0, dri 0 |
| GK | Sweeper Keeper | def 0.40, pac 0.25, pas 0.20 | phy 0.15, sho 0, dri 0 |
| GK | Classic Keeper | existing GK table | — |

Roll weights per position: specialized 30 / 30, balanced 40 (Complete Forward, Box-to-Box, Ball-Playing Defender, Classic Keeper).

**Rationale**: Spec mandates FWD trio; MID/DEF/GK mirror the same “specialist pair + complete” pattern without inventing PlayStyle keys.

**Alternatives considered**:
- FWD-only archetypes — fails FR-002.
- Many FIFA-style chem styles — YAGNI for v1.
- Tie archetypes to PlayStyle synergy table — out of scope (FR-014).

## R3 — Deterministic OVR balancing (replace while&lt;10)

**Decision**: After provisional stats:

1. Compute `current = calculate_true_ovr(position, stats, [], potential)`.
2. Optional bulk jump: estimate raw points ≈ `ceil(|target - current| / max(top_weight, 0.01))` and apply ± that many points split across the top-2 (up) or bottom-2 (down) attrs, clamped to [10, 99].
3. **Greedy fine-tune**: while `current != target` and a legal ±1 move exists on preferred attrs (then any adjustable attr as fallback), apply one bump and recompute. Prefer top-2 by archetype weight when raising; bottom-2 when lowering. Skip attrs with creation weight 0 (GK sho/dri).
4. If stuck (all attrs at bounds or potential ceiling blocks), stop at closest achievable — never silent “10 attempts then return wrong OVR”.

Remove the current loop that shifts *all* weighted attrs by ±1 for at most 10 attempts.

**Rationale**: True OVR is a floored weighted sum capped by potential; treating `delta` as raw stat points alone under-shoots. Greedy ±1 is deterministic, terminates (≤ ~500 steps worst case), and meets FR-006/008 “exact when bounds allow.” Product language “single-pass / O(1)” means no failed abandon loop, not a closed-form ignore of `floor()`.

**Alternatives considered**:
- Pure distribute `delta` points once with no verify — often misses target by 1–2 due to floor/weights.
- Keep while&lt;10 — fails SC-002.
- Binary search on a single attr — less faithful to “prefer primary/secondary” FR-007.

## R4 — Typed factory model vs `GachaPlayer`

**Decision**: Add `CreatedPlayerCard` (Pydantic) in `player_engine` as the factory return type (`role` required; `def` field via alias compatible with RPC). `GachaPlayer` gains `role: str = "Balanced"` and is built from `CreatedPlayerCard` in `_make_player`. Youth/regen may return models or `model_dump()` dicts consistently; prefer model at package boundary then dump at bot/RPC edge via `card_rpc_payload`.

**Rationale**: Constitution III + FR-009. Avoids a second competing schema: gacha pack UX keeps `GachaPlayer`; factory owns creation contract. Existing `card_rpc_payload` already adapters duck-typed players.

**Alternatives considered**:
- Factory returns `GachaPlayer` — pulls gacha naming into player_engine (wrong layer).
- Factory keeps `dict` — violates FR-009 / constitution.
- Rename everything to one shared model package — larger than needed.

## R5 — Pack configs location

**Decision**: New `packages/gacha/gacha/pack_configs.py` with:

```text
PackConfig(id, card_count, rarities[], rarity_weights[], positions[], position_weights[])
PACKS = {"standard": PackConfig(...60/30/8/2..., GK/DEF/MID/FWD 10/30/30/30)}
```

`generate_pack(n=None, pack_id="standard")` uses config (`n` overrides card_count when provided for tests). Unknown `pack_id` raises a small domain error (e.g. `UnknownPackConfigError`). Include a commented or unused `defender` example config **only if** it does not change `/store` — prefer documenting the shape in contracts without shipping a second live id unless tests need a fixture config.

**Rationale**: Spec FR-010 / SC-005. Rarity literals today live only in `generator.py`.

**Alternatives considered**:
- Put configs in `player_engine` — pack products are gacha’s concern.
- `game_config` DB rows for pack weights — heavier ops path; v1 is code config (tunable later).
- Ship Defender Pack in `/store` now — out of scope.

## R6 — Display surfaces

**Decision**: Add role to `gacha_claim_embed` (and marquee reveal if one-line cheap). Squad embed and player card “Role Style” already work once DB has role. No new hub controls.

**Rationale**: SC-003 / FR-012 without new commands.

## R7 — Call-site completeness

**Decision**: Treat these as mandatory consumers of the new factory:

| Caller | Path |
|--------|------|
| Daily pack | `gacha.generator.generate_pack` → store claim |
| Starter squad | `generate_starter_squad` → register |
| Youth intake | `youth_intake.generate_youth_intake_cards` → `process_youth_intake` |
| Regen pool | `regen_pool.generate_regen_from_retired` → `insert_scouting_pool_player` |

Grep after implement: `create_player_card` return type usages updated; no leftover reliance on missing `role`.

**Rationale**: FR-011 / SC-006; past “half-wired” bugs in this repo.

## R8 — Schema / verify

**Decision**: Migration `051_card_role_persistence.sql` + extend `verify_required_schema.sql` for `column:public.scouting_pool_players.role` (and keep existing `player_cards.role` if not already guarded). Function signatures unchanged (`jsonb` payloads only).

**Rationale**: Section 3b/8 AGENTS.md — no silent column use without migration/guard.

## R9 — Agent context script

**Decision**: Skip — repo has no `.specify` update-agent-context script. Plan + research artifacts are the design record.

**Alternatives considered**: Hand-edit AGENTS.md — not required for this feature.
