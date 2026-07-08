# apps/discord_bot/main.py
from __future__ import annotations
import asyncio
import json
import os
import logging
import time
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.discord_bot.core.thread_manager import ThreadManager
from apps.discord_bot.core.scheduler_jobs import weekly_league_reset_job, auto_sim_expired_fixtures_job, league_matchday_reminder_job, season_aging_job, youth_intake_job, regen_pool_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# #region agent log
_DEBUG_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "debug-690a24.log",
)


def _agent_debug(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    payload = {
        "sessionId": "690a24",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass
    logger.info("[DEBUG690a24] %s", json.dumps(payload))
# #endregion

# #region agent log
_DEBUG_3F48EC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "debug-3f48ec.log",
)


def _debug_3f48ec(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    *,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": "3f48ec",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_DEBUG_3F48EC_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass
# #endregion

# #region agent log
_DEBUG_8BE74E_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "debug-8be74e.log",
)


def _debug_8be74e(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    *,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": "8be74e",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_DEBUG_8BE74E_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass
# #endregion

# ponytail: module-level health server stays up across login retries so Render
# does not kill the process while Cloudflare 1015 cools down on shared IPs.
_render_health_site = None
_render_health_runner = None
_login_attempts_made = 0

# ponytail: Render shared IPs can stay Cloudflare-banned for 30+ min; short retries
# extend the ban. Override via DISCORD_LOGIN_INITIAL_DELAY_SECONDS / DISCORD_LOGIN_RETRY_DELAYS_SECONDS.
def _login_retry_delays() -> tuple[int, ...]:
    raw = os.environ.get("DISCORD_LOGIN_RETRY_DELAYS_SECONDS")
    if raw:
        return tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if os.environ.get("RENDER"):
        return (600, 900, 1200, 1800, 1800, 3600)
    return (30, 60, 120, 180, 300, 300, 300, 300)


def _initial_login_delay() -> int:
    raw = os.environ.get("DISCORD_LOGIN_INITIAL_DELAY_SECONDS")
    if raw is not None and raw != "":
        return max(0, int(raw))
    return 600 if os.environ.get("RENDER") else 0


async def _start_render_health_server(port: int) -> None:
    global _render_health_site, _render_health_runner
    if _render_health_site is not None:
        return

    from aiohttp import web

    async def handle_health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot": "connecting"})

    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)

    _render_health_runner = web.AppRunner(app)
    await _render_health_runner.setup()
    _render_health_site = web.TCPSite(_render_health_runner, "0.0.0.0", port)
    await _render_health_site.start()
    logger.info("Render health server listening on port %s (pre-login).", port)
    # #region agent log
    _agent_debug(
        "E",
        "main.py:_start_render_health_server",
        "health_server_listening_pre_login",
        {"port": port},
    )
    # #endregion


async def _stop_render_health_server() -> None:
    global _render_health_site, _render_health_runner
    if _render_health_site is not None:
        try:
            await _render_health_site.stop()
        except Exception as exc:
            logger.warning("Error stopping render health site: %s", exc)
        _render_health_site = None
    if _render_health_runner is not None:
        try:
            await _render_health_runner.cleanup()
        except Exception as exc:
            logger.warning("Error cleaning up render health runner: %s", exc)
        _render_health_runner = None


def _is_login_rate_limit(exc: discord.HTTPException) -> bool:
    if exc.status != 429:
        return False
    body = str(getattr(exc, "text", "") or getattr(exc, "message", "") or "")
    return (
        "1015" in body
        or "rate limited" in body.lower()
        or "cloudflare" in body.lower()
        or body.lstrip().startswith("<!doctype html")
    )


async def _run_bot_with_login_retry(token: str) -> None:
    global _login_attempts_made
    try:
        port = os.environ.get("PORT")
        if port:
            try:
                await _start_render_health_server(int(port))
            except ValueError:
                logger.error("Invalid PORT environment variable value: %s", port)

        retry_delays = _login_retry_delays()
        initial_delay = _initial_login_delay()
        if initial_delay > 0:
            logger.info(
                "Waiting %ds before first Discord login (Render Cloudflare cooldown).",
                initial_delay,
            )
            # #region agent log
            _agent_debug(
                "F",
                "main.py:_run_bot_with_login_retry",
                "initial_login_delay",
                {"seconds": initial_delay},
            )
            # #endregion
            await asyncio.sleep(initial_delay)

        last_exc: discord.HTTPException | None = None
        for attempt, delay in enumerate(retry_delays, start=1):
            _login_attempts_made = attempt
            bot = ElevenBossBot()
            # #region agent log
            _debug_3f48ec(
                "B",
                "main.py:_run_bot_with_login_retry",
                "bot_instance_created",
                {
                    "instance_id": bot._instance_id,
                    "attempt": attempt,
                    "pid": os.getpid(),
                },
            )
            # #endregion
            try:
                async with bot:
                    await bot.start(token, reconnect=True)
                return
            except discord.HTTPException as exc:
                if not _is_login_rate_limit(exc):
                    raise
                last_exc = exc
                body_preview = str(getattr(exc, "text", "") or "")[:500]
                # #region agent log
                _agent_debug(
                    "A",
                    "main.py:_run_bot_with_login_retry",
                    "discord_login_rate_limited",
                    {
                        "attempt": attempt,
                        "max_attempts": len(retry_delays),
                        "retry_in_seconds": delay,
                        "cloudflare_1015": "1015" in body_preview,
                    },
                )
                # #endregion
                if attempt >= len(retry_delays):
                    break
                logger.warning(
                    "Discord login rate-limited (attempt %d/%d); retrying in %ds. "
                    "Health server stays up so Render does not restart-loop.",
                    attempt,
                    len(retry_delays),
                    delay,
                )
                await asyncio.sleep(delay)

        if last_exc is not None:
            # #region agent log
            _agent_debug(
                "B",
                "main.py:_run_bot_with_login_retry",
                "login_retries_exhausted",
                {"attempts": len(retry_delays)},
            )
            # #endregion
            raise last_exc
    finally:
        await _stop_render_health_server()

# Load env variables
load_dotenv()

# Set up bot intents (no Message Content Intent required)
intents = discord.Intents.default()
intents.members = True  # Required to resolve user metadata / DM

class ElevenBossBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self._instance_id = uuid.uuid4().hex[:8]
        self._setup_hook_count = 0
        self._ready_count = 0
        self._commands_synced = False
        self.thread_manager: ThreadManager = ThreadManager(self)
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone="UTC")
        self.cogs_list = [
            "apps.discord_bot.cogs.onboarding_cog",
            "apps.discord_bot.cogs.squad_cog",
            "apps.discord_bot.cogs.player_cog",
            "apps.discord_bot.cogs.profile_cog",
            "apps.discord_bot.cogs.economy_cog",
            "apps.discord_bot.cogs.store_cog",
            "apps.discord_bot.cogs.development_cog",
            "apps.discord_bot.cogs.marketplace_cog",
            "apps.discord_bot.cogs.battle_cog",
            "apps.discord_bot.cogs.debug_cog",
            "apps.discord_bot.cogs.admin_cog",
            "apps.discord_bot.cogs.league_cog",
            "apps.discord_bot.cogs.leaderboard_cog",
        ]

    async def setup_hook(self) -> None:
        self._setup_hook_count += 1
        # #region agent log
        _agent_debug(
            "E",
            "main.py:setup_hook",
            "setup_hook_reached",
            {"discord_login_succeeded": True},
        )
        _debug_3f48ec(
            "D",
            "main.py:setup_hook",
            "setup_hook_entered",
            {
                "instance_id": self._instance_id,
                "setup_hook_count": self._setup_hook_count,
                "pid": os.getpid(),
            },
        )
        # #endregion

        # Load cogs
        for cog in self.cogs_list:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}", exc_info=True)

        from apps.discord_bot.views.level_reward_claim import ClaimAllLevelRewardsView
        self.add_view(ClaimAllLevelRewardsView())

        @self.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction,
            error: app_commands.AppCommandError,
        ) -> None:
            original = getattr(error, "original", error)
            cmd_name = interaction.command.qualified_name if interaction.command else "unknown"
            user_id = interaction.user.id if interaction.user else "?"

            if isinstance(original, discord.HTTPException) and original.status == 429:
                logger.warning(
                    "Rate limited on /%s for user %s (HTTP 429)",
                    cmd_name,
                    user_id,
                )
                from apps.discord_bot.core.view_helpers import safe_defer
                from apps.discord_bot.embeds.common_embeds import error_embed

                try:
                    if not interaction.response.is_done():
                        await safe_defer(interaction, ephemeral=True)
                    await interaction.followup.send(
                        embed=error_embed(
                            "Discord is temporarily rate-limiting requests. "
                            "Please try again in a minute."
                        ),
                        ephemeral=True,
                    )
                except discord.HTTPException:
                    pass
                return

            logger.error(
                "Unhandled app command error on /%s for user %s: %s",
                cmd_name,
                user_id,
                original,
                exc_info=original if isinstance(original, BaseException) else error,
            )
            from apps.discord_bot.embeds.common_embeds import error_embed

            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=error_embed("Something went wrong. Please try again."),
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        embed=error_embed("Something went wrong. Please try again."),
                        ephemeral=True,
                    )
            except discord.HTTPException:
                pass

        # Match recovery runs in on_ready once Discord is connected.

        # Register and start scheduler jobs
        # 0. Season aging (Monday 00:00 UTC) — before division reset
        self.scheduler.add_job(season_aging_job, "cron", day_of_week="mon", hour=0, minute=0, args=[self])
        self.scheduler.add_job(youth_intake_job, "cron", day_of_week="mon", hour=0, minute=0, args=[self])
        self.scheduler.add_job(regen_pool_job, "cron", day_of_week="mon", hour=0, minute=0, args=[self])
        # 1. Weekly league reset (Monday 00:00 UTC) — bot Division Rank ladder only
        self.scheduler.add_job(weekly_league_reset_job, "cron", day_of_week="mon", hour=0, minute=0, args=[self])
        # 2. Auto simulation of expired fixtures (every 10 minutes)
        self.scheduler.add_job(auto_sim_expired_fixtures_job, "interval", minutes=10, args=[self])
        # 3. League matchday closing reminders (hourly, deduped per matchday)
        self.scheduler.add_job(league_matchday_reminder_job, "interval", hours=1, args=[self])
        self.scheduler.start()
        logger.info("APScheduler initialized and jobs started.")

        # #region agent log
        local_cmds = sorted(
            getattr(cmd, "qualified_name", getattr(cmd, "name", str(cmd)))
            for cmd in self.tree.get_commands()
        )
        local_dupes = sorted({n for n in local_cmds if local_cmds.count(n) > 1})
        _debug_3f48ec(
            "E",
            "main.py:setup_hook",
            "local_tree_commands_after_cog_load",
            {
                "instance_id": self._instance_id,
                "command_count": len(local_cmds),
                "commands": local_cmds,
            },
        )
        _debug_8be74e(
            "E",
            "main.py:setup_hook",
            "local_tree_after_cog_load",
            {
                "instance_id": self._instance_id,
                "setup_hook_count": self._setup_hook_count,
                "command_count": len(local_cmds),
                "duplicate_names": local_dupes,
            },
        )
        # #endregion

    async def _start_web_server(self, port: int) -> None:
        from aiohttp import web
        
        async def handle_health(request):
            return web.json_response({
                "status": "ok",
                "bot": self.user.name if self.user else "connecting"
            })

        app = web.Application()
        app.router.add_get("/", handle_health)
        app.router.add_get("/health", handle_health)
        
        self._web_runner = web.AppRunner(app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(self._web_runner, "0.0.0.0", port)
        await self._web_site.start()
        logger.info(f"Web server started on port {port} for Render health checks.")
        # #region agent log
        _agent_debug(
            "E",
            "main.py:_start_web_server",
            "health_server_listening",
            {"port": port},
        )
        # #endregion

    async def close(self) -> None:
        """
        Cleanly closes the bot, stops background jobs, web server, and releases DB connections.
        """
        logger.info("Stopping background scheduler...")
        if hasattr(self, "scheduler") and self.scheduler.running:
            try:
                self.scheduler.shutdown()
            except Exception as e:
                logger.error(f"Failed to stop background scheduler: {e}", exc_info=True)

        logger.info("Releasing database client connection pools...")
        try:
            from apps.discord_bot.db.client import close_client
            await close_client()
        except Exception as e:
            logger.error(f"Failed to close Supabase client sessions: {e}", exc_info=True)

        await super().close()
        logger.info("Shutdown sequence completed.")

    async def on_ready(self) -> None:
        self._ready_count += 1
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        # #region agent log
        _agent_debug(
            "A",
            "main.py:on_ready",
            "discord_login_succeeded",
            {"attempt": _login_attempts_made},
        )
        _debug_3f48ec(
            "A",
            "main.py:on_ready",
            "on_ready_entered",
            {
                "instance_id": self._instance_id,
                "ready_count": self._ready_count,
                "commands_synced_flag": self._commands_synced,
                "pid": os.getpid(),
                "guild_id_env": os.environ.get("GUILD_ID"),
            },
        )
        # #endregion
        
        # Check if we should sync to a specific guild for local development
        guild_id = os.environ.get("GUILD_ID")
        try:
            local_cmds = sorted(
                getattr(cmd, "qualified_name", getattr(cmd, "name", str(cmd)))
                for cmd in self.tree.get_commands()
            )
            # #region agent log
            local_dupes = sorted({n for n in local_cmds if local_cmds.count(n) > 1})
            _debug_3f48ec(
                "C",
                "main.py:on_ready",
                "before_tree_sync",
                {
                    "instance_id": self._instance_id,
                    "ready_count": self._ready_count,
                    "sync_mode": "guild" if guild_id else "global",
                    "local_command_count": len(local_cmds),
                    "local_commands": local_cmds,
                },
            )
            _debug_8be74e(
                "A",
                "main.py:on_ready",
                "sync_decision",
                {
                    "instance_id": self._instance_id,
                    "ready_count": self._ready_count,
                    "commands_synced_flag": self._commands_synced,
                    "will_sync": True,
                    "sync_mode": "guild" if guild_id else "global",
                    "guild_id_env": guild_id,
                    "local_duplicate_names": local_dupes,
                    "pid": os.getpid(),
                },
            )
            # #endregion
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Command tree synchronized locally to Guild ID {guild_id} with {len(synced)} commands.")
            else:
                logger.info("Synchronizing application command tree globally...")
                synced = await self.tree.sync()
                logger.info(f"Command tree synchronized globally with {len(synced)} commands.")
            self._commands_synced = True
            synced_names = sorted(getattr(cmd, "name", str(cmd)) for cmd in synced)
            synced_dupes = sorted({n for n in synced_names if synced_names.count(n) > 1})
            # #region agent log
            _debug_3f48ec(
                "A",
                "main.py:on_ready",
                "after_tree_sync",
                {
                    "instance_id": self._instance_id,
                    "ready_count": self._ready_count,
                    "sync_mode": "guild" if guild_id else "global",
                    "synced_count": len(synced),
                    "synced_commands": synced_names,
                },
            )
            _debug_8be74e(
                "C",
                "main.py:on_ready",
                "after_tree_sync",
                {
                    "instance_id": self._instance_id,
                    "ready_count": self._ready_count,
                    "sync_mode": "guild" if guild_id else "global",
                    "synced_count": len(synced),
                    "synced_duplicate_names": synced_dupes,
                    "used_copy_global_to": bool(guild_id),
                },
            )
            # #endregion
        except Exception as e:
            # #region agent log
            _debug_3f48ec(
                "B",
                "main.py:on_ready",
                "tree_sync_failed",
                {
                    "instance_id": self._instance_id,
                    "ready_count": self._ready_count,
                    "error": str(e),
                },
            )
            # #endregion
            logger.error(f"Failed to sync command tree: {e}", exc_info=True)

        try:
            from apps.discord_bot.core.match_recovery import recover_interrupted_matches
            await recover_interrupted_matches(self)
        except Exception as e:
            logger.error(f"Match recovery failed on startup: {e}", exc_info=True)

        try:
            from apps.discord_bot.tasks.level_reward_notifier import notify_pending_level_rewards
            await notify_pending_level_rewards(self)
        except Exception as e:
            logger.error(f"Level reward notification failed on startup: {e}", exc_info=True)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        try:
            from apps.discord_bot.db.client import get_client
            from apps.discord_bot.core.guild_resolver import pause_seasons_for_guild

            db = await get_client()
            paused = await pause_seasons_for_guild(db, guild.id, "bot_removed")
            if paused:
                logger.info(
                    "Paused %d league season(s) after leaving guild %s (%s)",
                    paused,
                    guild.id,
                    guild.name,
                )
        except Exception:
            logger.exception("Failed to pause seasons after leaving guild %s", guild.id)

def main() -> None:
    # #region agent log
    _agent_debug(
        "B",
        "main.py:main:entry",
        "process_start",
        {
            "render_service": os.environ.get("RENDER_SERVICE_NAME"),
            "render_instance": os.environ.get("RENDER_INSTANCE_ID"),
            "port": os.environ.get("PORT"),
            "environment": os.environ.get("ENVIRONMENT"),
        },
    )
    _debug_3f48ec(
        "B",
        "main.py:main",
        "process_start",
        {
            "pid": os.getpid(),
            "guild_id_env": os.environ.get("GUILD_ID"),
            "environment": os.environ.get("ENVIRONMENT"),
            "render": bool(os.environ.get("RENDER")),
        },
    )
    _debug_8be74e(
        "B",
        "main.py:main",
        "process_start",
        {
            "pid": os.getpid(),
            "guild_id_env": os.environ.get("GUILD_ID"),
            "environment": os.environ.get("ENVIRONMENT"),
            "render": bool(os.environ.get("RENDER")),
        },
    )
    # #endregion

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN is missing from environment variables.")
        # #region agent log
        _agent_debug("D", "main.py:main", "missing_discord_token", {})
        # #endregion
        return

    # #region agent log
    stripped = token.strip()
    _agent_debug(
        "D",
        "main.py:main",
        "token_shape",
        {
            "raw_len": len(token),
            "stripped_len": len(stripped),
            "has_outer_whitespace": token != stripped,
            "looks_like_bot_token": stripped.count(".") == 2 and stripped.startswith(("MT", "OD", "MF", "Nz", "OT", "Mj")),
        },
    )
    # #endregion

    clean_token = stripped

    # #region agent log
    _agent_debug(
        "E",
        "main.py:main",
        "before_bot_run",
        {
            "health_server_starts_in": "pre_login_module_level",
            "port_configured": bool(os.environ.get("PORT")),
        },
    )
    # #endregion

    try:
        asyncio.run(_run_bot_with_login_retry(clean_token))
    except discord.HTTPException as exc:
        # #region agent log
        body_preview = str(getattr(exc, "text", "") or "")[:500]
        _agent_debug(
            "A",
            "main.py:main",
            "discord_login_http_exception",
            {
                "status": exc.status,
                "cloudflare_1015": "1015" in body_preview or "rate limited" in body_preview.lower(),
                "body_preview": body_preview[:300],
            },
        )
        _agent_debug(
            "B",
            "main.py:main",
            "login_failed_process_exiting",
            {"render_will_auto_restart": bool(os.environ.get("RENDER"))},
        )
        # #endregion
        raise

if __name__ == "__main__":
    main()
