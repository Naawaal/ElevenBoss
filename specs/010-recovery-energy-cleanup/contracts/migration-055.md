# Contract: Migration 055 — energy + recovery config

**Feature**: `010-recovery-energy-cleanup`  
**File**: `supabase/migrations/055_recovery_energy_cap_cleanup.sql` (planned)

## Must include

1. **CHECK relax** on `players.energy` and `players.training_energy` to allow values up to **120** (drop old `<= 100` constraints by name, add new).
2. Upsert/update `game_config`:
   - `energy_max` = `120`
   - `fatigue_recovery_energy` = `5` (**DO UPDATE**, not only DO NOTHING)
3. `UPDATE players SET max_energy = 120 WHERE max_energy < 120`
4. Column defaults: `action_energy`, `energy`, `max_energy`, `training_energy` → 120 where safe
5. `CREATE OR REPLACE` latest `process_recovery_session` with fallback `get_game_config_int('fatigue_recovery_energy', 5)`
6. `CREATE OR REPLACE` latest `sync_action_energy` and `apply_club_economy` with fallback `get_game_config_int('energy_max', 120)` (copy from current 028/047 bodies; only change fallback + leave behavior otherwise)
7. `CREATE OR REPLACE register_new_player` (or only the INSERT constants) so new clubs get `max_energy = 120` (and starting energy consistent)
8. Schema guard: config keys present OR function fallbacks verified; extend `verify_required_schema.sql` only if new objects added (likely none)

## Must not

- Drop Hospital tables/RPCs
- Change `fatigue_recovery_session` (40)
- Change drill energy config keys
