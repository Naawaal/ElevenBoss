# Quickstart & Validation Guide: Feature 054 — Instant PvP Backfill and Ghost Managers

**Branch**: `054-instant-pvp-backfill` | **Date**: 2026-08-05

## Overview

This guide details the step-by-step verification commands and test scenarios to validate Instant PvP Backfill and Ghost Manager matchmaking end-to-end.

---

## Environment Setup & Prerequisites

1. Confirm PostgreSQL database environment is available via `DATABASE_URL` in `.env`.
2. Ensure existing tests pass:
   ```bash
   pytest tests/test_pvp_matchmaking.py
   ```

---

## Runnable Validation Scenarios

### Scenario 1: Ghost Match Creation for Lone Searcher

**Goal**: Verify a manager queuing alone initiates a Ghost match within 15 seconds.

1. **Apply Migration 103**:
   ```bash
   python scratch/apply_migration_103.py
   ```
2. **Populate Test Ghost Snapshots**:
   ```sql
   SELECT refresh_pvp_ghost_snapshot(999001); -- Mock manager snapshot
   ```
3. **Execute Queue Test**:
   ```bash
   pytest tests/test_pvp_ghost_backfill.py -k "test_single_searcher_ghost_backfill"
   ```
4. **Expected Outcome**:
   - `try_match_pvp_queue` returns `matched = true`, `opponent_mode = 'ghost'`, `run_id` created.
   - Ghost owner `999001` incurs zero energy cost and zero state mutation.

---

### Scenario 2: Atomic Race Condition (Live Pair Wins over Ghost)

**Goal**: Verify a live human joining at 9.9 seconds pairs with searcher A before A claims a ghost.

1. **Execute Race Test**:
   ```bash
   pytest tests/test_pvp_ghost_backfill.py -k "test_live_pairing_wins_race_over_ghost"
   ```
2. **Expected Outcome**:
   - Exactly one match run is created.
   - `opponent_mode = 'live'`, pairing both live managers.
   - Ghost candidate is not claimed.

---

### Scenario 3: Calibrated AI Fallback

**Goal**: Verify queue falls back to Calibrated Ranked AI when zero ghost snapshots exist.

1. **Execute AI Fallback Test**:
   ```bash
   pytest tests/test_pvp_ghost_backfill.py -k "test_ai_backfill_fallback"
   ```
2. **Expected Outcome**:
   - `try_match_pvp_queue` returns `matched = true`, `opponent_mode = 'ai_backfill'`.
   - Calibrated AI squad generated with matching XI rating.

---

### Scenario 4: One-Sided Ghost Match Finalization

**Goal**: Verify rewards and history are applied to challenger only with Ghost multipliers.

1. **Execute Finalization Test**:
   ```bash
   pytest tests/test_pvp_ghost_backfill.py -k "test_ghost_finalization_one_sided"
   ```
2. **Expected Outcome**:
   - Challenger receives 0.75x positive LP and 0.85x coins.
   - Exactly 1 history row is written.
   - Ghost owner suffers 0 LP/coin loss.
   - No `manager_rivalries` updated.
