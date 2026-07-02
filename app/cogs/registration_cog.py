import logging
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from app.config import config
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.registration_cog")


class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /register — new guided onboarding flow ─────────────────────────────

    @app_commands.command(
        name="register",
        description="Register your football club and get your squad of 25 players.",
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def register(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        if config.REGISTRATION_ONBOARDING_ENABLED:
            # Guided onboarding flow
            await interaction.response.defer(ephemeral=True)
            try:
                from app.services.onboarding_service import OnboardingService
                await OnboardingService.start_or_resume_registration(interaction)
            except Exception as e:
                logger.error(f"register (onboarding): {e}", exc_info=e)
                capture_exception(e)
                await interaction.followup.send(
                    "Something went wrong starting your registration. Our team has been notified.",
                    ephemeral=True,
                )
        else:
            # Legacy one-shot /register kept for backwards compatibility while the
            # feature flag is disabled.  Remove when REGISTRATION_ONBOARDING_ENABLED=true
            # becomes the permanent default.
            await interaction.response.send_message(
                "⚠️ Registration via slash command is temporarily disabled while we roll out "
                "the new guided onboarding experience. Please try again shortly.",
                ephemeral=True,
            )

    # ── on_interaction — global router for onboarding buttons ──────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        Routes component interactions (button clicks, select menus) whose scope
        is "onboarding" to the appropriate OnboardingService handler.
        All other interactions are ignored here (handled by club_cog.py or discord.py).
        """
        if interaction.type != discord.InteractionType.component:
            return

        raw_id = interaction.data.get("custom_id", "")
        if not raw_id.startswith("fcm:v1:onboarding:"):
            return

        try:
            from app.onboarding.custom_ids import parse_onboarding_id
            action, session_id_or_short, nonce = parse_onboarding_id(raw_id)
        except ValueError:
            logger.warning(f"on_interaction: malformed onboarding custom_id: {raw_id!r}")
            return

        # Resolve full session_id from the DB using the short prefix if it is legacy (string)
        if isinstance(session_id_or_short, str):
            session_id = await self._resolve_session_id(
                interaction.guild_id, interaction.user.id, session_id_or_short
            )
            if session_id is None:
                await interaction.response.send_message(
                    "This setup session has expired. Please run `/register` again.",
                    ephemeral=True,
                )
                return
        else:
            session_id = session_id_or_short

        try:
            from app.services.onboarding_service import OnboardingService

            if action == "next":
                # nonce carries the step name
                await OnboardingService.handle_next_step(
                    interaction=interaction,
                    session_id=session_id,
                    current_step=nonce,
                )
            elif action == "club_name":
                from app.onboarding.modals import ClubNameModal
                await interaction.response.send_modal(ClubNameModal(session_id=session_id))
            elif action == "finish":
                await OnboardingService.handle_finish(
                    interaction=interaction,
                    session_id=session_id,
                )
            else:
                logger.warning(f"on_interaction: unknown onboarding action: {action!r}")
        except Exception as e:
            logger.error(f"on_interaction: onboarding handler error: {e}", exc_info=e)
            capture_exception(e)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Something went wrong. Please try again.", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "Something went wrong. Please try again.", ephemeral=True
                    )
            except Exception:
                pass

    async def _resolve_session_id(
        self,
        guild_id: int | str,
        user_id: int | str,
        short_id: str,
    ) -> uuid.UUID | None:
        """
        Look up the full session UUID by querying for the user's active session
        and verifying the short prefix matches. (Legacy fallback)
        """
        try:
            from app.db.session import get_session
            from app.repositories import onboarding_repository as onb_repo
            async with get_session() as db_session:
                onb_session = await onb_repo.get_active_session(db_session, guild_id, user_id)
                if not onb_session:
                    return None
                # Verify the short prefix matches (prevents spoofing across users)
                actual_short = str(onb_session.id).replace("-", "")[:8]
                if actual_short != short_id:
                    logger.warning(
                        f"_resolve_session_id: short_id mismatch "
                        f"expected={actual_short!r} got={short_id!r}"
                    )
                    return None
                return onb_session.id
        except Exception as e:
            logger.error(f"_resolve_session_id: {e}", exc_info=e)
            capture_exception(e)
            return None


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
