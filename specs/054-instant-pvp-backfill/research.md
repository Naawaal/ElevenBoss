# Phase 0 Research: Feature 054 — Instant PvP Backfill and Ghost Managers

**Branch**: `054-instant-pvp-backfill` | **Date**: 2026-08-05

## Technical Decisions & Rationale

### 1. Opponent Selection Hierarchy & Timeline
- **Decision**: 
  - 0–5 seconds: Search for close live-human opponent (Division diff = 0, LP diff ±100, OVR diff ±4).
  - 5–10 seconds: Widen live-human search (Division diff ±1, LP diff ±200, OVR diff ±7).
  - 10 seconds: Perform final atomic live-human check inside transaction.
  - If no live human found: Select best eligible Ghost Manager snapshot.
  - If no ghost available: Construct division-calibrated Ranked AI opponent.
- **Rationale**: 10 seconds allows sufficient time for active concurrent users to pair naturally while keeping total queue wait strictly under 15 seconds (target 5–12s).
- **Alternatives Considered**: 
  - *Fixed 30s timeout*: Rejected because user testing indicates drop-off occurs after 15s in quick mobile/Discord manager games.
  - *Scheduled PvP windows only*: Rejected because it does not provide 24/7 on-demand play.

### 2. Ghost Snapshot Immutability & One-Sided Storage
- **Decision**: 
  - Store ghost snapshots in a dedicated `pvp_ghost_snapshots` table, captured upon completion of eligible competitive matches or squad updates.
  - When a ghost match is created, copy the entire ghost snapshot payload into `match_runs.squad_snapshot`.
  - The match execution is completely single-sided: only the searching challenger's state is mutated at finalization.
- **Rationale**: Completely isolates offline ghost owners from unwanted side effects (LP drops, energy drains, notifications) and guarantees match recovery immutability.
- **Alternatives Considered**: 
  - *Live fetch of ghost owner's squad*: Rejected because the owner's squad might be invalid, injured, or sold mid-match.
  - *Deduct LP from ghost owner on loss*: Rejected to avoid surprising offline managers with unexplained rank demotions.

### 3. Server-Enforced Mode Classification & Multipliers
- **Decision**: 
  - Retain `match_type = 'pvp'` for all Ranked matches, and introduce `opponent_mode` (`'live'`, `'ghost'`, `'ai_backfill'`).
  - Compute base LP/coins/XP using existing formulas, then apply server-side multipliers:
    - **Live Human**: 1.00x coins, 1.00x XP, 1.00x pos/neg LP.
    - **Ghost Manager**: 0.85x coins, 0.90x XP, 0.75x pos LP, 0.50x neg LP.
    - **Ranked AI Backfill**: 0.70x coins, 0.75x XP, 0.50x pos LP, 0.25x neg LP.
- **Rationale**: Keeps Ranked PvP rewards attractive while preventing LP inflation and rewarding live-human encounters most heavily.
- **Alternatives Considered**: 
  - *Equal rewards for Ghost and Live*: Rejected due to risk of LP inflation without a corresponding human loser.

### 4. Atomic Concurrency Control
- **Decision**: 
  - Execute queue matching and ghost claiming inside `try_match_pvp_queue` using `FOR UPDATE SKIP LOCKED`.
  - Lock searcher `v_a`. If `backfill_after <= NOW()`, check live candidates first. If none, select candidate snapshot from `pvp_ghost_snapshots` with block, cooldown, and daily cap filters.
- **Rationale**: Eliminates race conditions between simultaneous searchers, cancellations, and backfill triggers.
- **Alternatives Considered**: 
  - *Application-level python lock*: Rejected because multiple Discord bot worker processes or APScheduler jobs could run concurrently.

### 5. Rivalry System Bounding
- **Decision**: 
  - Keep `manager_rivalries` and head-to-head records strictly live-human only (`opponent_mode = 'live'`).
  - Track ghost encounters in `pvp_ghost_encounters` solely for cooldowns and daily limits.
- **Rationale**: Rivalries represent mutual human competition; facing a static ghost snapshot repeatedly should not inflate or distort head-to-head records.
