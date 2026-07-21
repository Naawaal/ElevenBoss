# apps/discord_bot/main.py
from __future__ import annotations
import asyncio
import os
import logging
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.discord_bot.core.thread_manager import ThreadManager
from apps.discord_bot.core.scheduler_jobs import weekly_league_reset_job, auto_sim_expired_fixtures_job, league_state_machine_job, league_lifecycle_wake_job, league_matchday_reminder_job, season_aging_job, youth_intake_job, regen_pool_job, daily_recovery_job, academy_growth_job, transfer_listing_expiry_job, weekly_payroll_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

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
            await asyncio.sleep(initial_delay)

        last_exc: discord.HTTPException | None = None
        for attempt, delay in enumerate(retry_delays, start=1):
            _login_attempts_made = attempt
            bot = ElevenBossBot()
            try:
                async with bot:
                    await bot.start(token, reconnect=True)
                return
            except discord.HTTPException as exc:
                if not _is_login_rate_limit(exc):
                    raise
                last_exc = exc
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
            "apps.discord_bot.cogs.admin_cog",
            "apps.discord_bot.cogs.league_cog",
            "apps.discord_bot.cogs.leaderboard_cog",
        ]

    async def setup_hook(self) -> None:
        self._setup_hook_count += 1

        # Load cogs
        for cog in self.cogs_list:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}", exc_info=True)

        from apps.discord_bot.views.level_reward_claim import ClaimAllLevelRewardsView
        from apps.discord_bot.views.support_legendary_claim import ClaimSupportLegendaryView
        self.add_view(ClaimAllLevelRewardsView())
        self.add_view(ClaimSupportLegendaryView())

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
        self.scheduler.add_job(daily_recovery_job, "cron", hour=0, minute=5, args=[self])
        self.scheduler.add_job(league_state_machine_job, "cron", hour=0, minute=5, args=[self])
        self.scheduler.add_job(league_lifecycle_wake_job, "interval", minutes=5, args=[self])
        self.scheduler.add_job(weekly_payroll_job, "cron", day_of_week="mon", hour=0, minute=5, args=[self])
        self.scheduler.add_job(academy_growth_job, "cron", hour=0, minute=10, args=[self])
        self.scheduler.add_job(transfer_listing_expiry_job, "interval", hours=1, args=[self])
        self.scheduler.start()
        logger.info("APScheduler initialized and jobs started.")

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
        
        # Check if we should sync to a specific guild for local development
        guild_id = os.environ.get("GUILD_ID")
        try:
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
        except Exception as e:
            logger.error(f"Failed to sync command tree: {e}", exc_info=True)

        try:
            from apps.discord_bot.core.match_recovery import recover_interrupted_matches
            await recover_interrupted_matches(self)
        except Exception as e:
            logger.error(f"Match recovery failed on startup: {e}", exc_info=True)

        try:
            from apps.discord_bot.core.league_recovery import startup_recovery_pass
            from apps.discord_bot.db.client import get_client
            await startup_recovery_pass(self, await get_client())
        except Exception as e:
            logger.error("League lifecycle recovery failed on startup: %s", e, exc_info=True)

        try:
            from apps.discord_bot.tasks.level_reward_notifier import notify_pending_level_rewards
            await notify_pending_level_rewards(self)
        except Exception as e:
            logger.error(f"Level reward notification failed on startup: {e}", exc_info=True)

        try:
            from apps.discord_bot.tasks.support_legendary_notifier import (
                notify_support_legendary_rewards,
            )
            await notify_support_legendary_rewards(self)
        except Exception as e:
            logger.error(f"Support legendary notification failed on startup: {e}", exc_info=True)

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
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN is missing from environment variables.")
        return

    clean_token = token.strip()

    try:
        asyncio.run(_run_bot_with_login_retry(clean_token))
    except discord.HTTPException:
        raise

if __name__ == "__main__":
    main()
