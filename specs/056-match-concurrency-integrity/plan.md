# Implementation Plan: Match Concurrency & Squad Locking Integrity

**Branch**: `056-match-concurrency-integrity` | **Feature Spec**: [`spec.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/spec.md)

---

## Technical Context

- **Target Systems**: `apps/discord_bot/cogs/battle_cog.py`, `apps/discord_bot/cogs/squad_cog.py`, `apps/discord_bot/core/match_runs.py`, `apps/discord_bot/middleware/match_lock.py`, `apps/discord_bot/core/pvp_match.py`, `supabase/migrations/108_match_concurrency_integrity.sql`.
- **Database Layer**: Supabase PostgreSQL 15+ async RPCs for atomic run creation and lock acquisition.
- **Language / Framework Constraints**: Python 3.13 strict type annotations, Pydantic models for data crossing app boundaries, zero `discord` imports in `packages/`.
- **Dependencies**: `discord.py >= 2.7.0`, `supabase >= 2.0.0`, `pydantic >= 2.0.0`, `apscheduler >= 3.10.0`.

---

## Constitution Check

- [x] **Principle I: Monorepo Architecture**: Pure game logic remains in `packages/`. Discord cogs/views stay in `apps/discord_bot/`.
- [x] **Principle II: Database Transactions via Async Supabase**: All match run creations, lock acquisitions, and squad mutations run inside atomic Supabase RPC stored procedures.
- [x] **Principle III: Strict Typing & Pydantic**: All snapshot schemas and RPC parameters use explicit types and Pydantic models.
- [x] **Principle IV: Discord Slash Commands**: Ephemeral responses for all rejected match initiation or squad mutation interactions.
- [x] **Principle VII: Simplicity & YAGNI**: Focus purely on cross-mode match concurrency, run-linked locks, SQL guards, and snapshot immutability.

---

## Phase 0: Research & Architecture Decisions

See [`research.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/research.md) for full rationale on:
1. **Canonical ID Ordering for Lock Acquisition**: Sorting participant IDs (`LEAST(home, away)`, `GREATEST(home, away)`) before acquiring `match_locks` rows inside `start_friendly_match` to eliminate deadlock possibilities.
2. **SQL Guard Exception Contract**: Raising `P0001` with message `manager_in_active_match` in `set_formation_and_assignments` and `swap_squad_players` so Python UI handlers can catch and map to UI disablement cleanly.
3. **Ghost Owner Exemption**: Confirming that Ghost Manager snapshot backfills lock ONLY the active human challenger, leaving the offline ghost owner completely unlocked.

---

## Phase 1: Design Artifacts

- **Data Model**: [`data-model.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/data-model.md)
- **RPC Contracts**: [`contracts/match_concurrency_rpc.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/contracts/match_concurrency_rpc.md)
- **Validation Quickstart**: [`quickstart.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/quickstart.md)

---

## Proposed Changes & Affected Files

### Database Migrations

#### [NEW] [`108_match_concurrency_integrity.sql`](file:///d:/Python/Discord%20Bots/ElevenBoss/supabase/migrations/108_match_concurrency_integrity.sql)
- Alters `match_locks` table to add foreign key `run_id UUID REFERENCES match_runs(id) ON DELETE CASCADE`.
- Adds UNIQUE constraint on `match_locks.discord_id`.
- Creates stored procedure `assert_manager_match_available(p_discord_id BIGINT)`.
- Updates `acquire_match_lock(p_discord_id BIGINT, p_lock_type TEXT, p_run_id UUID)`.
- Creates stored procedure `start_friendly_match(...)` for atomic 2-manager lock and run creation.
- Creates stored procedure `start_single_manager_match(...)` for atomic single-manager lock and run creation.
- Updates stored procedures `set_formation_and_assignments` and `swap_squad_players` to raise `manager_in_active_match` if a `match_locks` row exists for `p_discord_id`.
- Updates `reconcile_orphaned_match_locks` to treat `streaming`, `completing`, and `recovering` runs as active.

#### [MODIFY] [`verify_required_schema.sql`](file:///d:/Python/Discord%20Bots/ElevenBoss/supabase/scripts/verify_required_schema.sql)
- Includes schema checks for `assert_manager_match_available`, `start_friendly_match`, and `start_single_manager_match` RPCs.

---

### App Layer (`apps/discord_bot/`)

#### [MODIFY] [`middleware/match_lock.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/apps/discord_bot/middleware/match_lock.py)
- Adds `reject_if_in_match(interaction, db, *manager_ids)` command guard helper.
- Uses `assert_manager_match_available` RPC.

#### [MODIFY] [`core/match_runs.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/apps/discord_bot/core/match_runs.py)
- Implements `build_ephemeral_match_snapshot()` helper.
- Enforces non-empty 11-card squad snapshots on `create_ephemeral_run()`.

#### [MODIFY] [`cogs/battle_cog.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/apps/discord_bot/cogs/battle_cog.py)
- Calls `reject_if_in_match` on Friendly challenge creation, Friendly acceptance, Bot Battle, AI Practice, and Ranked queue entry.
- Replaces non-atomic friendly match creation with `start_friendly_match` RPC.
- Replaces non-atomic bot match creation with `start_single_manager_match` RPC.

#### [MODIFY] [`cogs/squad_cog.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/apps/discord_bot/cogs/squad_cog.py)
- Catches `manager_in_active_match` SQL exceptions in formation/swap callbacks, updates view state (`is_locked = True`), disables formation/swap buttons, and returns an ephemeral warning.

---

## Verification Plan

### Automated Tests
- Create `tests/test_match_concurrency_integrity.py` with 18 comprehensive regression scenarios.
- Run `pytest tests/test_match_concurrency_integrity.py -v`.
- Run `python scratch/verify_schema_full.py`.

### Manual Verification
- Execute test scenarios detailed in [`quickstart.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/quickstart.md).
