import logging
import platform
import time
import discord
from discord import app_commands
from discord.ext import commands
from app.utils.embeds import info_embed, success_embed

logger = logging.getLogger("app.cogs.core_cog")

class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="ping", description="Checks the bot's latency and responsiveness.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, interaction: discord.Interaction):
        # Gateway latency
        latency_ms = round(self.bot.latency * 1000)
        
        # Calculate API response round-trip latency
        start_time = time.perf_counter()
        await interaction.response.send_message(
            embed=info_embed("Pinging...", "Calculating round-trip latency..."), 
            ephemeral=True
        )
        end_time = time.perf_counter()
        api_latency_ms = round((end_time - start_time) * 1000)

        # Update message with real numbers
        embed = success_embed(
            "Pong!",
            f"**Gateway Latency:** `{latency_ms}ms`\n"
            f"**REST API Latency:** `{api_latency_ms}ms`"
        )
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="info", description="Displays general information and statistics about ElevenBoss.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def info(self, interaction: discord.Interaction):
        uptime_seconds = int(time.time() - self.start_time)
        uptime_str = self._format_uptime(uptime_seconds)

        fields = [
            {"name": "Library", "value": f"discord.py v{discord.__version__}", "inline": True},
            {"name": "Python Version", "value": platform.python_version(), "inline": True},
            {"name": "Guilds", "value": str(len(self.bot.guilds)), "inline": True},
            {"name": "Uptime", "value": uptime_str, "inline": False},
        ]
        
        embed = info_embed(
            title="ElevenBoss Information",
            description="A highly scalable, structured Discord bot built with Sentry integration.",
            fields=fields
        )
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="test_error", description="Intentionally triggers an exception to test Sentry integration.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.default_permissions(administrator=True)
    async def test_error(self, interaction: discord.Interaction):
        await interaction.response.send_message("Triggering test error... Check logs and Sentry.", ephemeral=True)
        # Raise an exception to be caught globally and forwarded to Sentry
        raise RuntimeError("Test error triggered via /test_error command.")

    @app_commands.command(name="db-health", description="Checks the connectivity and status of the PostgreSQL database.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.default_permissions(administrator=True)
    async def db_health(self, interaction: discord.Interaction):
        from app.db.health import check_db_health
        from app.utils.embeds import success_embed, error_embed

        await interaction.response.defer(ephemeral=True)

        health_result = await check_db_health()

        if health_result["ok"]:
            embed = success_embed("Database Connected", health_result["message"])
        else:
            embed = error_embed("Database Connection Failed", health_result["message"])

        await interaction.edit_original_response(embed=embed)

    def _format_uptime(self, seconds: int) -> str:
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))
