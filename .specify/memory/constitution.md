# ElevenBoss Constitution

## Core Principles

### I. Monorepo Architecture (NON-NEGOTIABLE)

ElevenBoss is a **Python monorepo** with strict separation of concerns across two layers:

- **`apps/discord_bot/`** — The Discord gateway layer. Contains all `discord.py` cogs, views, embeds, and slash command handlers. This is the only layer permitted to import `discord`.
- **`packages/`** — Stateless, framework-agnostic game logic packages (`match_engine`, `economy`, `gacha`, `leagues`, `energy`). These packages are pure Python business logic.

**Absolute Prohibition**: Packages under `packages/` MUST NEVER import `discord`, `discord.py` UI components, or any application-layer module from `apps/`. Violation of this boundary is a blocking defect. Packages communicate results via Pydantic models returned to the app layer.

All packages are installed as local editable installs (`pip install -e packages/<name>`) so cross-package imports resolve cleanly without path manipulation.

### II. Database: Supabase (PostgreSQL) — Async Only

- The `supabase` Python async client is the **only** permitted database interface. No raw `psycopg2` or `asyncpg` calls at the application level.
- **All financial mutations** (currency debits/credits, player purchases, level-ups) and **all state mutations** (squad saves, match results, division changes) MUST be wrapped in Supabase/PostgreSQL transactions using `rpc()` calls to stored procedures or explicit `BEGIN`/`COMMIT` via the REST API batch endpoint.
- Database schema migrations are managed via Supabase migrations (SQL files). No ORM-level migration tools (e.g., Alembic) are used.

### III. Strict Typing & Pydantic Validation (NON-NEGOTIABLE)

- All Python files MUST include `from __future__ import annotations` and be written with full, strict type hints.
- All data crossing a module boundary (e.g., from `match_engine` to the Discord bot) MUST be represented as a **Pydantic `BaseModel`**.
- `Any` types are forbidden except in explicitly justified adapter/glue code. `TYPE_CHECKING` imports are acceptable.
- Pydantic models serve as the schema contract between packages; changing a model field is a breaking change and requires updating all consumers.

### IV. Discord Interaction Model — Slash Commands Only

- **No Message Content Intent**. The bot operates exclusively via application commands (slash commands, context menus, buttons, selects).
- All user-facing interactions MUST be ephemeral or deferred correctly to prevent Discord interaction timeout (3-second window).
- Cogs are registered as `app_commands.Group` subclasses or use `@app_commands.command` decorators directly.

### V. Background Tasks — APScheduler

- All time-based automation (energy regeneration, weekly league resets, daily gacha reset) MUST use `APScheduler` with `AsyncIOScheduler`.
- Scheduled jobs run inside the bot's event loop. Jobs that perform database writes must handle their own error recovery and log failures without crashing the scheduler.
- Scheduler state is ephemeral; jobs are re-registered on each bot startup from configuration.

### VI. Error Handling & Observability

- All Discord command handlers MUST have a top-level `try/except` that catches unexpected exceptions, logs them with full traceback via Python `logging`, and returns a user-friendly ephemeral error embed — never a raw Python traceback in a Discord message.
- Packages must raise typed, domain-specific exceptions (e.g., `InsufficientEnergyError`, `InvalidFormationError`) rather than generic `Exception`.
- Structured logging (`logging.getLogger(__name__)`) is mandatory in every module.

### VII. Simplicity & YAGNI

- No feature is built speculatively. Every system implemented must be traceable to a user story in `spec.md`.
- Dependencies are kept minimal. A new `pip` dependency requires justification against the alternatives.

## Technology Stack (Locked)

| Concern | Library / Service | Version Constraint |
|---|---|---|
| Discord Gateway | `discord.py` | `>=2.7.0` |
| Database Client | `supabase` (async) | `>=2.0.0` |
| Data Validation | `pydantic` | `>=2.0.0` |
| Background Tasks | `apscheduler` | `>=3.10.0` |
| Python Runtime | CPython | `>=3.11` |
| Database Backend | Supabase (PostgreSQL 15+) | Hosted / self-hosted |

## Governance

- This constitution supersedes all other practices, README instructions, or individual preferences.
- Any amendment to a Core Principle requires: (1) documented rationale, (2) explicit update to this file, (3) migration plan for existing code.
- All PRs are reviewed against this constitution. A PR that violates Principle I (package boundary) or Principle II (non-transactional financial writes) is rejected without exception.
- Runtime development guidance lives in `.specify/memory/` and `.github/prompts/`.

**Version**: 1.0.0 | **Ratified**: 2026-07-04 | **Last Amended**: 2026-07-04
