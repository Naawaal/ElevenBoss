# Research & Architectural Decisions: Match Concurrency & Squad Locking Integrity

**Feature**: [`spec.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/spec.md) | [`plan.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/plan.md)

---

## 1. Deadlock Prevention via Canonical Manager ID Ordering

### Problem
When Manager A challenges Manager B to a Friendly match, and Manager B accepts, two manager IDs must be locked simultaneously inside `match_locks`. If two inverse challenges are accepted simultaneously (Manager A accepting Manager B while Manager B accepts Manager A), acquiring locks in arbitrary order can cause a PostgreSQL transaction deadlock (`ERRCODE = 40P01`).

### Decision
Inside `start_friendly_match` PL/pgSQL RPC, participant IDs are sorted deterministically before acquiring locks:
```sql
v_first_id := LEAST(p_home_id, p_away_id);
v_second_id := GREATEST(p_home_id, p_away_id);
```
Lock acquisition always attempts `v_first_id` followed by `v_second_id`.

### Rationale
Enforcing a global lock ordering guarantees strict serializability and completely eliminates SQL deadlock possibilities during simultaneous acceptance attempts.

---

## 2. SQL-Enforced Squad Mutation Guard Contract

### Problem
Currently, Python UI views check `match_locks` before allowing formation changes or player swaps. However, if a manager opens a squad view before a match starts, and keeps it open after kickoff, clicking a button or executing direct database API calls can bypass Python UI checks.

### Decision
Extend `set_formation_and_assignments` and `swap_squad_players` PL/pgSQL functions with an explicit lock check at line 1 of the function body:
```sql
IF EXISTS (
    SELECT 1 FROM public.match_locks WHERE discord_id = p_discord_id
) THEN
    RAISE EXCEPTION USING
        ERRCODE = 'P0001',
        MESSAGE = 'manager_in_active_match';
END IF;
```

### Rationale
Database-level enforcement guarantees integrity regardless of how the SQL function is invoked (Discord UI, stale button, CLI script, or external API call).

---

## 3. Unlocked Status for Offline Ghost Managers

### Problem
In Ranked PvP backfill, a live manager may be paired against a "Ghost Manager" (a frozen snapshot of an offline real manager's squad).

### Decision
Ghost owners must NOT have a row inserted into `match_locks`. Only the active human challenger receives a `match_locks` entry.

### Rationale
Facing a ghost is a single-sided challenge against frozen historical data. The offline ghost owner suffers zero LP loss, zero fatigue, zero energy drain, and must remain 100% free to edit their squad or play matches when they log in.
