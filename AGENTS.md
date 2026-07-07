# ElevenBoss Development Rules for AI Agents

This document contains strict constraints and architecture rules for AI agents operating on this repository. Every agent MUST adhere to these rules without exception.

---

## 1. The Monorepo Rule
* The `packages/` directory contains **pure Python logic** only.
* Agents are **strictly forbidden** from importing `discord` or `discord.ext` anywhere inside `packages/`.
* Any Discord-related integration, UI rendering, cogs, or interaction logic must remain in `apps/discord_bot/`.

## 2. The State Rule
* Packages under `packages/` must remain completely stateless regarding external databases.
* They **must not** instantiate database clients (such as Supabase, SQLAlchemy, etc.) or perform direct database IO.
* Packages should accept raw data or Pydantic models as input, perform the necessary calculations/logic, and return clean Pydantic models or primitive types.

## 3. The Database Rule
* All complex mutations (such as user registration, player transactions/purchases, league resets) must be handled via **atomic Supabase RPCs** (stored procedures) or safe, transaction-like **upserts**.
* **Never** write application-level loops that execute multiple sequential `INSERT` or `UPDATE` queries if they can be combined or batched. This minimizes network round-trips and prevents half-applied states.

## 3b. The Schema Rule (do not break production DB)
* **Columns are defined only in `supabase/migrations/`** — never `SELECT`, `INSERT`, or `UPDATE` a column name in SQL/RPCs unless it exists in a migration `ALTER TABLE` / `CREATE TABLE` in this repo. Constants (e.g. `daily_drill_limit := 20`) are **not** columns.
* **When replacing an RPC**, diff against the previous migration version; do not drop calls like `sync_training_energy` or swap column names without checking `015_hardening_schema.sql` and peers.
* **Every schema change** gets a new numbered migration file; never edit an already-applied migration in place on remote — add a forward fix migration instead (repo source files may be corrected for fresh installs).
* **After migrations**, run `supabase/scripts/verify_required_schema.sql` (or rely on the guard block in the latest migration) before shipping bot changes that depend on new tables/columns.
* **Extend the guard lists** in `verify_required_schema.sql` and migration `022+` when adding tables/columns the bot or RPCs require.

## 4. The UI Rule
* Discord slash commands must invoke `await interaction.response.defer(ephemeral=True)` (or `ephemeral=False` as appropriate) **immediately** at the start of command execution.
* This prevents Discord's built-in 3-second API timeout limit from being exceeded during database requests or external processing.

## 5. The SDD (Spec-Driven Development) Rule
* Any new features, command flows, database schema changes, or architectural decisions **MUST** be designed and documented in the `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` files **BEFORE** writing any code.
* Implementation must strictly adhere to the approved specifications and technical plans.
* Any refinements or deviations introduced during coding must be retroactively reconciled in the SDD documents so they remain the single source of truth for the codebase.

---

# Ponytail, lazy senior dev mode

You are a lazy senior developer. Lazy means efficient, not careless. The best code is the code never written.

Before writing any code, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern that's already here, don't re-write it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.

The ladder runs after you understand the problem, not instead of it: read the task and the code it touches, trace the real flow end to end, then climb.

Bug fix = root cause, not symptom: a report names a symptom. Grep every caller of the function you touch and fix the shared function once — one guard there is a smaller diff than one per caller, and patching only the path the ticket names leaves a sibling caller still broken.

Rules:

- No abstractions that weren't explicitly requested.
- No new dependency if it can be avoided.
- No boilerplate nobody asked for.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins, but only once you understand the problem. The smallest change in the wrong place isn't lazy, it's a second bug.
- Question complex requests: "Do you actually need X, or does Y cover it?"
- Pick the edge-case-correct option when two stdlib approaches are the same size, lazy means less code, not the flimsier algorithm.
- Mark intentional simplifications with a `ponytail:` comment. If the shortcut has a known ceiling (global lock, O(n²) scan, naive heuristic), the comment names the ceiling and the upgrade path.

Not lazy about: understanding the problem (read it fully and trace the real flow before picking a rung, a small diff you don't understand is just laziness dressed up as efficiency), input validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs (the platform is never the spec ideal, a clock drifts, a sensor reads off), anything explicitly requested. Lazy code without its check is unfinished: non-trivial logic leaves ONE runnable check behind, the smallest thing that fails if the logic breaks (an assert-based demo/self-check or one small test file; no frameworks, no fixtures). Trivial one-liners need no test.

(Yes, this file also applies to agents working on the ponytail repo itself. Especially to them.)

---

## 6. Workspace Boundaries (do not mess up the repo)

### Where code lives

| Path | Purpose | Agent rules |
|------|---------|-------------|
| `packages/` | Pure game logic (no Discord, no DB IO) | Add formulas/gates here; export via `__init__.py` |
| `apps/discord_bot/` | Discord cogs, views, embeds, DB calls | All `discord` imports stay here |
| `supabase/migrations/` | **Only** place schema/RPCs are defined | New numbered file per change; never patch remote-applied migrations in place |
| `supabase/scripts/verify_required_schema.sql` | Post-migration guard | Extend when adding tables/columns/RPCs the bot needs |
| `tests/` | Unit tests (repo root) | Not under `packages/*/tests/` unless that package already uses it |
| `scripts/` | Ops/admin tools (idempotent, documented) | For backfills and one-off maintenance |
| `scratch/` | Local apply/check scripts, experiments | **Never** import from `scratch/` in production code; safe to add, don't treat as API |
| `.specify/specs/v1.0.0/` | SDD source of truth | Update `spec.md` + `plan.md` **before** new features |

### Never do without explicit user request

* Commit, push, force-push, or amend git history
* Edit `.env`, credentials, or commit secrets
* Delete or rewrite already-applied migration files on the assumption remote matches
* Add debug/agent instrumentation and leave it in cogs after the task is done
* Create markdown docs the user did not ask for (`README` dumps, ADRs, etc.)
* Import `discord` into `packages/` or put business logic inside cogs when it belongs in `packages/`
* Reference DB columns in Python/SQL that are not defined in `supabase/migrations/`
* Loop `INSERT`/`UPDATE` per row when an RPC or batch upsert exists
* Ship bot changes that call new RPCs before migration + `verify_required_schema.sql` pass

### Secrets & local files

* `DATABASE_URL`, Discord tokens, and Supabase keys live in `.env` only — never log or commit them
* Debug session logs (`debug-*.log`) are ephemeral; do not commit them

---

## 7. Progression & Leveling (US-23 — do not regress)

Player XP/level/skill points are **centralized**. Agents must not reintroduce old bypasses.

* **Single XP pipe:** all XP (match, drill, fusion) goes through RPC `apply_card_xp`. Never `UPDATE player_cards SET xp = xp + N` or `level = level + 1` in app code or ad-hoc SQL.
* **Pure formulas:** `packages/player_engine/player_engine/progression.py` is the source of truth for curves and rewards (`match_xp_reward`, `fusion_xp_reward`, `drill_xp_reward`, `level_from_xp`). Bot code **calls** these; it does not duplicate formulas.
* **Match XP wiring:** use `apps/discord_bot/core/match_xp.py` → `build_process_match_result_rpc()` and RPC `process_match_result(..., p_xp_amounts)`. Do **not** pass hardcoded flat XP (e.g. `15`) from cogs.
* **Drills:** `process_stat_drill` grants XP only — no direct `+1` stat bumps.
* **Fusion:** `train_with_fodder` grants fusion XP via `apply_card_xp` — no direct level/stat bump; respect `fusion_daily_log` cap.
* **Skill allocation:** `allocate_skill_point` enforces POT caps and `skill_points_spent`; use `can_allocate_skill_point()` in packages before UI hints.
* **Retroactive rewards:** `pending_level_rewards` + `claim_pending_level_rewards`; claim uses **current `owner_id`**, not stale `club_id`; scaled 75% cap 18 (US-24).
* **Daily caps (US-24):** match XP 100/card/day; drills 5/card/day + 20/club; allocation 15/card/day during pacing window.
* **`/claim-rewards`** fallback when DMs disabled — use **`/development` hub Claim button** instead.
* **Evolution ticks:** `process_match_result` already calls `tick_evolution_match_progress` — do not double-call it on the same cards in the same match flow (friendly matches were a past bug).

### Economy v2 (US-25 — do not regress)

* **Single coin pipe:** all coin mutations go through RPC `apply_club_economy` (match payouts, drills, fusion, login, refills). Never direct `players.coins` UPDATE in cogs.
* **Config:** tunables live in `game_config` table (migration `028_economy_foundation.sql`); packages mirror defaults in `packages/economy/economy/flows.py`.
* **Action energy:** unified `players.action_energy` via `sync_action_energy` (+1 per 6 min); legacy `energy`/`training_energy` dual-written during transition.
* **Match wiring:** `apps/discord_bot/core/economy_rpc.py` — `apply_match_economy`, `sync_action_energy`, `compute_*_match_coins`; `battle_cog` uses `match_run_id` as idempotency key.
* **Agent sales:** `process_agent_sale` enforces `agent_sale_daily_cap` (default 10/day).
* **Player faucets:** `/store` hub (`store_cog.py`) for `claim_daily_login` + `purchase_energy_refill` — **not** `/development`.
* **Development hub:** drills, fusion, evolutions, skill allocation, claim level rewards only (`development_cog.py`).
* **Fusion sink:** `train_with_fodder` charges `fusion_coins` (default 200) via `apply_club_economy`.
* **Ops tuning:** edit `game_config` in Supabase, `scripts/simulate_economy.py`, or ledger SQL — **no** Discord admin economy slash command.
* **Player-facing changelog:** [`change_log.md`](change_log.md) at repo root (update when shipping economy/progression changes).

When touching any progression or economy RPC, **grep all callers** in `apps/discord_bot/` and `supabase/migrations/` before merging.

---

## 8. Migration Workflow (production-safe)

1. Design in SDD → new file `supabase/migrations/NNN_descriptive_name.sql`
2. If replacing an RPC signature, `DROP FUNCTION IF EXISTS` the old overload(s) first (Postgres keeps multiple signatures otherwise)
3. End migration with schema guard `DO $$ … $$` **or** extend `verify_required_schema.sql`
4. Apply locally/remote via `scratch/apply_migration_NNN.py` (psycopg + `DATABASE_URL`) — pattern in existing scratch scripts
5. Verify: `python scratch/verify_schema_full.py` or `psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql`
6. Only then wire bot/cog changes that depend on new columns/RPCs

**RLS on new exposed tables (required):** If a migration creates a table the bot reads/writes via the Data API (`anon` key), ship **`ENABLE ROW LEVEL SECURITY` + policies in the same migration file**. Minimum: `SELECT` + any `INSERT`/`UPDATE`/`DELETE` the bot performs. Target roles: `anon, authenticated, service_role`. Never leave RLS on with zero policies — SELECT returns empty and INSERT fails with `42501`. See `030_league_members_rls.sql` for the pattern; `031_rls_policy_guard.sql` fails deploy if a bot-required table regresses.

**Schema guard pitfall:** `function:public.foo` entries use `split_part(req.obj, ':', 2)` for the function name — not `:3` (that was a real production rollback bug on migration 025). Policy entries use `policy:public.<table>.<policy_name>` with `split_part` on the segment after `policy:` (see `verify_required_schema.sql`).

**Constants vs columns:** values like `daily_drill_limit := 20` belong inside RPC bodies, not as new columns unless the migration adds them.

---

## 9. Discord Bot Conventions

* Defer interactions immediately (`interaction.response.defer`) before DB/RPC work
* **Hub commands:** `/development` = progression; `/store` = daily login + energy refills; do not duplicate faucet buttons across hubs
* Persistent views (e.g. claim buttons) must be registered in `main.py` via `bot.add_view(...)`
* Level-up DMs: use `_notify_match_level_ups` / `level_reward_notifier` patterns — don't invent one-off DM logic per cog
* Match types (`bot`, `friendly`, `league`) use different `match_type` multipliers in `match_xp_reward` — pass the correct type
* Match **coins** use `economy_rpc.apply_match_economy` (not hardcoded cog `players.update` on `coins`)

---

## 10. Verification Checklist (before saying “done”)

* [ ] Migration applied and `verify_required_schema.sql` passes
* [ ] New pure logic has a small test in `tests/` (or extends an existing file)
* [ ] No new `discord` imports under `packages/`
* [ ] No hardcoded XP/stat/coin bypasses outside RPCs
* [ ] Economy changes: `game_config` + migration `028+` applied; `tests/test_economy_flows.py` passes
* [ ] Player-facing copy updated in `change_log.md` when shipping economy/progression UX changes
* [ ] Grep confirms all callers of changed RPCs/helpers are updated
* [ ] Debug instrumentation removed unless user is actively debugging
* [ ] SDD updated if behavior diverged from spec

