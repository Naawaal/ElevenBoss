# Feature 056 — Match Concurrency & Squad Locking Integrity

**Scope**: Cross-mode match concurrency prevention, atomic run-linked locking, SQL-enforced squad mutation guards, and immutable kickoff snapshot simulation.

---

## 1. Executive Summary & User Value

Currently, squad formation and player swap UI callbacks check `match_locks` in Python. However, because lock acquisition and match creation are not performed in a single atomic database transaction across all match entry paths (especially Friendly challenges and AI Practice), a manager can occasionally enter two simultaneous matches or modify their squad after kickoff.

This feature establishes **atomic, run-linked match concurrency protection** and **SQL-enforced squad mutation guards**. Every active human participant in any match mode (Friendly, Bot Battle, Ranked PvP, League) is guaranteed to hold exactly one durable `match_locks` row linked to an active `match_runs` record. Squad edits are blocked at both the Python UI layer and inside Supabase PL/pgSQL stored procedures. All simulations use immutable kickoff snapshots, and locks are released strictly upon terminal match settlement.

---

## 2. User Scenarios & Primary Flows

### Scenario 1: Rejection of Dual Match Entry
- **Given** a manager is currently in an active match (Friendly, Bot, Ranked, or League),
- **When** they attempt to challenge a friend, join a Ranked PvP queue, start a Bot Battle, or enter AI Practice,
- **Then** the bot immediately returns a clear, ephemeral message:  
  `🔒 You are already in a match. Finish your current match before starting another battle.`

### Scenario 2: Rejection of Friendly Acceptance when Challenger or Opponent is Busy
- **Given** Manager A issues a Friendly challenge to Manager B,
- **When** Manager B clicks **Accept**,
- **Then** the server atomically verifies both Manager A and Manager B in canonical ID order.
- **If** either manager is already locked in a match, the acceptance fails atomically with an ephemeral notice and no match run is created.

### Scenario 3: Squad Mutation Guarding on Stale UI or Direct RPC Invocation
- **Given** a manager has an open `/squad` UI view and subsequently enters a match,
- **When** they attempt to change formation or swap players from the stale view (or call `set_formation_and_assignments` / `swap_squad_players` directly),
- **Then**:
  1. The PL/pgSQL procedure raises an exception (`ERRCODE = 'P0001', MESSAGE = 'manager_in_active_match'`).
  2. The Python callback catches the exception, updates the view state (`is_locked = True`), disables formation/swap buttons, and sends a user-friendly ephemeral message.

### Scenario 4: Immutable Kickoff Snapshot Simulation
- **Given** any match is initiated (Friendly, Bot, Ranked, Ghost, or League),
- **When** the match run is created,
- **Then** an immutable 11-card squad snapshot is captured and stored in `match_runs.squad_snapshot`.
- **And** the match simulation reads exclusively from `squad_snapshot` without re-querying live `player_cards` table state during play.

---

## 3. Functional Requirements

### FR-001: Atomic Multi-Mode Match Availability RPC
- The database schema must provide `public.assert_manager_match_available(p_discord_id BIGINT)` returning structured JSON (`{"available": true}` or `{"available": false, "lock_type": "...", "run_id": "...", "message": "..."}`).
- `acquire_match_lock` must accept `(p_discord_id BIGINT, p_lock_type TEXT, p_run_id UUID)` and enforce a UNIQUE constraint on `discord_id` so a manager cannot hold more than one active lock.

### FR-002: Atomic Friendly Match Start RPC
- Friendly match creation must be handled via an atomic RPC `start_friendly_match` that:
  1. Locks the challenge record.
  2. Acquires `match_locks` for both managers in canonical ID order (`LEAST(home, away)`, `GREATEST(home, away)`) to prevent deadlocks.
  3. Rejects run creation if either manager is already locked.
  4. Inserts `match_runs` and attaches both locks to the run in a single transaction.

### FR-003: Atomic Single-Manager Match Start RPC
- Single-manager match entry (Bot Battle, AI Practice) must be handled via an atomic RPC `start_single_manager_match` that acquires one `match_locks` row and creates `match_runs` atomically.
- Ranked matchmaking (Live human pairing, Ghost backfill, AI backfill) must acquire challenger/participant locks inside the existing matcher transaction. Ghost owners must remain 100% unlocked.

### FR-004: Database-Enforced Squad Mutation Guards
- PL/pgSQL procedures `set_formation_and_assignments` and `swap_squad_players` must check `match_locks` for `p_discord_id` at the beginning of the transaction.
- If a lock exists, the procedure must abort immediately with error code `P0001` (`manager_in_active_match`).

### FR-005: Immutable Squad Snapshot Contract
- A general snapshot builder `build_ephemeral_match_snapshot()` must construct complete 11-card simulation models (attributes, positions, tactics, card IDs, DOB, fatigue, injury).
- Non-empty snapshots are mandatory for all human match types. Simulation must read exclusively from `match_runs.squad_snapshot`.

### FR-006: Stale UI Revalidation & Disablement
- Discord UI interactions in `squad_cog.py` (`SquadFormationView`, `SquadSwapView`, `SquadHubView`) must catch `manager_in_active_match` exceptions, update internal state to `is_locked = True`, and edit the view to disable formation/swap buttons.

### FR-007: Standardized Terminal Lock Release
- Locks are released ONLY upon reaching terminal run states (`completed`, `abandoned`, `cancelled-before-kickoff`, `administratively-recovered`).
- Intermediate states (`streaming`, `completing`, `recovering`) MUST retain locks. Thread archival or Discord client disconnects must NOT release locks.

### FR-008: Hardened Restart Recovery & Orphan Reconciliation
- `reconcile_orphaned_match_locks` on bot startup must treat `streaming`, `completing`, and `recovering` runs as active.
- Startup match recovery passes (friendly, bot, ranked, league) must run BEFORE orphan lock reconciliation.

---

## 4. Success Criteria & Verification

| Criteria | Metric | Verification Method |
|---|---|---|
| Concurrent Match Prevention | 100% rejection of dual-match attempts | Integration test attempting simultaneous match starts across modes |
| SQL Squad Mutation Guard | 100% rejection of formation/swap RPCs while locked | SQL integration test calling `set_formation_and_assignments` under active lock |
| Snapshot Isolation | 0% live squad data leakage during simulation | Modifying `player_cards` mid-match and verifying engine simulation result is unaffected |
| Ghost Owner Exemption | 100% unlocked status for offline ghost managers | Verifying ghost owner can edit squad while their ghost snapshot is being played |
| Terminal Settlement Release | 100% lock cleanup on terminal status | Checking `match_locks` count is 0 after `completed` or `abandoned` status |

---

## 5. Assumptions & Constraints

- **Monorepo Discipline**: All pure Python logic and data structures remain inside `packages/` or stateless helpers; Discord UI handlers remain strictly in `apps/discord_bot/`.
- **Async Supabase Only**: All database mutations use atomic RPCs or Supabase client calls.
- **No Direct Table Deletes Outside Terminal Settlement**: `match_locks` rows are created and deleted exclusively by server RPCs (`acquire_match_lock`, `release_match_lock`, `complete_*_run`, `abandon_match_run`).
