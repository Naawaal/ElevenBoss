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

---

## 5. Discord Components V2 UI & Session Guidelines
- **Components V2 Only**: Interactive screens must use the Components V2 system (setting `IS_COMPONENTS_V2` message flag). Do not mix V2 messages with legacy `content` or `embeds`.
- **Text as Components**: Render all text inside `TextDisplay` (type `10`) components.
  * Note that `TextDisplay` components must use the `"content"` key (not `"text"`) for their markdown text content.
  * Use a `Section` (type `9`) layout component only when you need to pair the text with an `accessory` (such as a button or thumbnail). If no accessory is needed, place the `TextDisplay` directly inside the `Container` (type `17`) instead of wrapping it in a Section.
- **Bypass Serialization via V2View**: Use `V2View` from `app/ui/components.py` to transmit raw Components V2 payload dicts to Discord.
- **Compact Custom IDs**: All button/select `custom_id`s must use the compact colon-separated format `fcm:v1:<scope>:<action>:<target>:<nonce>`. Always encode and decode custom IDs via `encode_custom_id` and `decode_custom_id` in `app/ui/custom_ids.py` to enforce length limits (max 100 chars) and white-listed scopes/actions.
- **Global Event Interception**: Do not bind callbacks directly on View classes. All button and select clicks must be routed through the global `on_interaction` event listener in `app/cogs/club_cog.py`.
- **Interaction and Session Validation**: Every interaction callback must validate:
  1. The guild exists (no DMs allowed).
  2. The session has not expired and the clicking user is the verified owner of the session (using `ui_session_manager`).
  3. The requested player or club belongs to the manager (verified via the service layer).
- **No Explicit Null Content/Embeds on Edits**: When editing a Components V2 message using `edit_original_response()` or `edit_message()`, do **NOT** pass `content=None` or `embed=None`. Discord's API rejects messages that contain any top-level `"content"` or `"embeds"` fields when the `IS_COMPONENTS_V2` flag is set. Omit these parameters entirely from the method calls so they are excluded from the PATCH payload.
- **Inline Image Rendering (Media Gallery)**: To render an uploaded attachment image inline as a visual preview rather than a downloadable file card, use the **Media Gallery** component (type `12`) with nested structures:
  `{"type": 12, "items": [{"media": {"url": "attachment://filename.png"}, "description": "Alt Text"}]}`.
  Do not use the `File` component (type `13`), as it renders as a generic download widget. Note that both components require the file URL to be wrapped in an object under a `"url"` key, not passed as a raw string.
- **Font Resiliency**: When using image rendering libraries like Pillow, always wrap font loading calls (`ImageFont.truetype()`) in a try-except block catching `IOError`, falling back to `ImageFont.load_default()` to guarantee cross-platform runtime safety.

---

## 6. Match Simulation, Gameplay Engine, and Standings Guidelines
- **Deterministic Simulation**: All gameplay simulation calculations (under `app/engine/`) must be entirely deterministic and reproducible via a provided seed. Never use `random.randint()`, global `random.seed()`, or system time in simulation logic. Always instantiate and pass a local `random.Random(seed)` instance.
- **Idempotency & Scheduler Locks**: Matchday simulation must check and create a running lock record in the `scheduler_runs` table using a unique lock key (format: `matchday:{guild_id}:{season_id}:{week}`) within a single transaction to prevent parallel executions.
- **Lineup Resiliency**: If a club has no active or valid lineup prior to simulation, the service layer must automatically construct a fallback starting XI using squad players (e.g. via `build_auto_lineup`) and save it to the database before running the match simulation.
- **Atomic Standings Consistency**: Updates to match results, standings, fixtures status, and scheduler run states must all occur atomically within a single database transaction context to prevent desynchronized statistics.
