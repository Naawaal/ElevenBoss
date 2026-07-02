"""
Discord modal used to collect the club name during onboarding.
"""
import logging
import uuid
import discord

logger = logging.getLogger("app.onboarding.modals")


class ClubNameModal(discord.ui.Modal, title="Name Your Club"):
    """
    Single-field modal that collects the user's desired club name.
    On submit, delegates to OnboardingService.handle_club_name_modal.
    """

    club_name: discord.ui.TextInput = discord.ui.TextInput(
        label="Club Name",
        placeholder="e.g. Arsenal FC, Red Lions, City United",
        min_length=3,
        max_length=40,
        required=True,
        style=discord.TextStyle.short,
    )

    def __init__(self, session_id: uuid.UUID):
        super().__init__()
        self.session_id = session_id

    async def on_submit(self, interaction: discord.Interaction):
        """Delegate to OnboardingService to validate and save the club name."""
        from app.services.onboarding_service import OnboardingService
        await OnboardingService.handle_club_name_modal(
            interaction=interaction,
            session_id=self.session_id,
            raw_name=self.club_name.value,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"ClubNameModal error: session_id={self.session_id}, error={error}", exc_info=error)
        from app.error_reporting import capture_exception
        capture_exception(error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong while saving your club name. Please try again.",
                    ephemeral=True,
                )
        except Exception:
            pass
