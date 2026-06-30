# ElevenBoss — Multiplayer Football Management Discord Bot

ElevenBoss is a Python-based Discord bot designed for a multiplayer football management simulation. It features a scalable, modular architecture built for production stability, structured logging, and automated runtime crash reporting.

## Project Architecture

The bot is structured to separate concerns, keeping Discord presentation logic detached from the core simulation engine and database layers:

```text
ElevenBoss/
  app/
    __init__.py
    bot.py                 # Bot startup, lifecycle hooks, and slash command tree error handler
    config.py              # Centralized environment variable loader and validator
    logging_config.py      # Structured rotating file/console logging configuration
    error_reporting.py     # Sentry-based crash/error reporting abstraction

    cogs/                  # Discord slash commands and event listeners only
      __init__.py
      core_cog.py          # Core bot slash commands (/ping, /info, /test_error)

    db/                    # Database configurations & session management (Future)
      __init__.py
    models/                # Database entities and declarations (Future)
      __init__.py
    repositories/          # Data access patterns and DB interactions (Future)
      __init__.py
    services/              # Core business logic layer (Future)
      __init__.py
    engine/                # Pure football simulation mechanics (Future)
      __init__.py
    scheduler/             # APScheduler jobs for automated matchdays (Future)
      __init__.py
    ui/                    # Interactive embeds, buttons, select menus, pagination (Future)
      __init__.py
    utils/                 # Shared helper methods and utilities
      __init__.py
      embeds.py            # Polished UI color palettes and embed helpers

  logs/                    # Local runtime logs directory
    .gitkeep               # Preserves logs folder structure in git

  tests/                   # Unit and integration test suite
    __init__.py

  .env.example             # Template for configuration environment variables
  .gitignore               # Custom Git ignore configuration
  requirements.txt         # Package dependencies
  README.md                # Project documentation
  main.py                  # CLI application entry point
```

## Setup & Installation

### 1. Prerequisites
- Python 3.8 or higher installed on your system.

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in the required values:
```bash
# On Windows PowerShell:
Copy-Item .env.example .env
# On Linux/macOS:
cp .env.example .env
```

Review and configure the variables:
- `DISCORD_TOKEN`: Your Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
- `COMMAND_PREFIX`: Fallback prefix for text-based commands (if any).
- `ENVIRONMENT`: Tags events in Sentry (e.g. `development`, `staging`, `production`).
- `LOG_LEVEL`: Log level (e.g. `DEBUG`, `INFO`, `WARNING`, `ERROR`).
- `SENTRY_DSN`: Sentry project DSN (optional).

### 3. Install Dependencies
Create a virtual environment, activate it, and install required libraries:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

## Running the Bot

### Normal Execution
Start the bot normally:
```bash
python main.py
```
> [!NOTE]
> During local development (`ENVIRONMENT=development` and `GUILD_ID` configured in `.env`), the bot will **automatically sync slash commands** to your test server guild on startup, removing the need to run the manual sync command.


### Syncing Application Slash Commands
Slash commands must be synced to Discord. Use the built-in CLI flags to sync and exit:
```bash
# Sync commands globally (may take up to 1 hour to propagate across Discord)
python main.py --sync global

# Sync commands to a specific guild instantly (requires GUILD_ID in .env)
python main.py --sync guild
```

## Core Features

### 1. Structured Logging
The bot configures robust rotating logs under the `logs/` directory:
- `logs/app.log`: General application log capturing all events at `LOG_LEVEL` and above. Max size is 5MB, rotating up to 5 backups.
- `logs/error.log`: Dedicated error log capturing `WARNING`, `ERROR`, and `CRITICAL` levels.
- Console Logging: Formatted console output for local development.

### 2. Runtime Error Reporting
Error reporting is abstracted in `app/error_reporting.py`:
- Initializes Sentry dynamically if `SENTRY_DSN` is specified in `.env`.
- Integrates with the bot's slash command error handler to log uncaught errors.
- Gracefully runs in no-op mode locally if no Sentry configuration is present.
- Features `capture_exception(error)` and `capture_message(message)` helpers.
- Filters out user-side errors (cooldowns, check failures, missing permissions) to keep Sentry issues focused on genuine system exceptions.

## Development Notes
- **Slash Commands Only**: The bot is configured to use Discord Slash Commands. No prefix command routes are registered.
- **Intents**: The bot runs using least-privilege `discord.Intents.default()`. No privileged intents are enabled.
