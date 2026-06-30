# ElevenBoss — Project-Scoped Rules and Guidelines

This file outlines the architectural boundaries and conventions for the ElevenBoss Discord Bot project. Any AI agents modifying this codebase must adhere strictly to these guidelines.

---

## 1. Project Architecture & Concerns Separation

Always follow the clean folder structure. Do not mix business logic, database queries, or gameplay simulation with Discord representation layer:
- **`app/cogs/`**: Exclusively contains Discord Slash Commands and event listeners.
- **`app/services/`**: Exclusively contains business logic and high-level workflows.
- **`app/repositories/`**: Exclusively contains database query logic.
- **`app/engine/`**: Exclusively contains pure football simulation calculations (completely independent of Discord and Database).
- **`app/db/`**: Handles connections, session factories, and database health.
- **`app/ui/`**: Stores embeds, interactive menus, buttons, and custom views.

---

## 2. Discord Bot Guidelines
- **Slash Commands Only**: The bot is configured for slash commands. Do not register message-based prefix commands.
- **Least-Privilege Intents**: Only use `discord.Intents.default()`. Do not enable privileged intents (like Message Content or Server Members) unless explicitly requested.
- **Development Auto-Sync**: The bot automatically copy-syncs slash commands to the guild specified by `GUILD_ID` in `.env` when `ENVIRONMENT` is `development` on startup.

---

## 3. Database & Concurrency Guidelines
- **SQLAlchemy 2.0**: All database tables must inherit from the Declarative Base class `Base` inside `app/db/base.py`.
- **Async Operations Only**: Always perform database actions asynchronously using `asyncpg`. Never write blocking synchronous SQL queries.
- **Session Lifecycles**: Always use the `get_session()` transaction context manager from `app/db/session.py` to create isolated, transaction-safe database sessions. Never share a global database session across multiple concurrent Discord commands.
- **Automatic Migrations**: Database migrations are automatically checked and applied to `head` on startup via `app/db/migrations.py`. Do not call blocking migration commands in async event loops.

---

## 4. Error Handling & Sentry Guidelines
- **Sentry Integration**: Always route exceptions to Sentry using `capture_exception(error)` from `app/error_reporting.py`.
- **Benign Errors**: Filter out user-facing errors (cooldowns, missing permissions, invalid arguments) in `on_app_command_error` before reporting to Sentry to avoid alert fatigue.
- **Local Resilience**: Sentry must remain optional. If `SENTRY_DSN` is empty, Sentry runs in no-op mode without breaking local execution.
- **Sentry MCP Server**: Utilize the Sentry MCP server integration (`sentry/*` tools like `search_issues`, `get_sentry_resource`, and `analyze_issue_with_seer`) to fetch stack traces, debug production errors, and run AI-based root-cause analysis directly from Sentry.

