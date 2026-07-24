# Research: Match Engine V3 Production Rollout

**Feature**: `044-match-v3-rollout` | **Date**: 2026-07-24  
**Companion**: [spec.md](./spec.md) · [plan.md](./plan.md)

---

## 1. Current-state findings

### Already shipped (`041` + `083`)

| Capability | Evidence |
|------------|----------|
| Per-type flags | `game_config`: `match_engine_v3_{bot,league,friendly}` default `0` |
| Kickoff pin | `resolve_engine_version` → `create_ephemeral_run` / `create_league_run` |
| V3 sim + recovery | `collect_match_events_v3`, recovery branches on `engine_version` |
| Post-match explainability hook | `battle_cog` builds `explanation` from `project_explanation` for bot + league finalize |
| Embed field | “🔍 How it was decided” when `explanation` present |

### Gaps this feature closes

1. **Flags still off in prod** — managers never see V3.  
2. **`project_explanation` is a Phase-0 stub** — goals/chances only; tip lines often show raw `type` (`GOAL`) not readable football copy.  
3. **Ops soak/rollback** not packaged as a runnable checklist for solo cutover.  
4. **Changelog** not yet written for live enable.

### Audit context (post-043)

Marketplace intelligence is complete enough; next retention ROI is the match climax, not more market flash.

---

## 2. Decisions

### D1 — Rollout feature, not engine rewrite

- **Decision**: No re-architecture of NSS v3.  
- **Rationale**: `041` plan status: implementation complete; next step was bot-flag soak.  
- **Alternatives**: Rebuild tactics (rejected — already done).

### D2 — Cutover order bot → league → friendly

- **Decision**: Same as `041` dual-run contract.  
- **Rationale**: Bot isolates integrity risk; league is weekly retention after confidence.  
- **Alternatives**: League-first (rejected — amplifies blast radius).

### D3 — Config flags only

- **Decision**: Flip existing keys; no new slash command / admin cog.  
- **Rationale**: YAGNI; ops already use `game_config`.  
- **Alternatives**: Env-only staging override (optional additive, not required).

### D4 — Immutable kickoff pin

- **Decision**: Keep current create-run pin semantics.  
- **Rationale**: Prevents mid-run engine swap on flag flip.  
- **Alternatives**: Hot-swap (rejected — integrity risk).

### D5 / D6 — Enrich explainability projector + Discord copy

- **Decision**: Expand `project_explanation` to prefer high-signal events (goals, decisive chances, decision-window / tactical changes when present); Discord tip lines use `causal_hint` / humanized text, not bare `type`. Empty → omit field or minimal headline only.  
- **Rationale**: Spec US2; current stub under-delivers once flags are on.  
- **Alternatives**: Flag-only with stub UI (rejected — weak retention story).

### D7 — Settlement independence

- **Decision**: Never gate settle-once on embed success.  
- **Rationale**: US-42.4; already settlement-before-present for bot.  
- **Alternatives**: None acceptable.

### D8 — No new migration by default

- **Decision**: Schema from `083` is sufficient.  
- **Rationale**: Flags + `engine_version` + events exist.  
- **Alternatives**: Soak metrics table (defer).

### D9 — Documented soak gate

- **Decision**: Checklist in quickstart + soak contract before league flag.  
- **Rationale**: Spec FR-003 / SC-004.  
- **Alternatives**: Informal “looks fine” (rejected).

### D10 — Explicit non-goals

- **Decision**: No marketplace, wages, Redis, Ranked, squad Tactics Soon in this feature.  
- **Rationale**: Audit prioritization; YAGNI.

---

## 3. Resolved clarifications

No open NEEDS CLARIFICATION — codebase already provides flag/pin/hook paths; unknowns reduced to copy enrichment scope (frozen in D5/D6).
)
