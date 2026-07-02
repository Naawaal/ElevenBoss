"""
Tests for the onboarding registration cog — custom_id routing.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import discord


def make_button_interaction(custom_id: str, user_id: int = 12345, guild_id: int = 99999):
    interaction = MagicMock()
    interaction.type = discord.InteractionType.component
    interaction.data = {"custom_id": custom_id}
    interaction.guild_id = guild_id
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.client = MagicMock()
    return interaction


@pytest.mark.asyncio
async def test_non_onboarding_custom_id_is_ignored():
    """Interactions with non-onboarding custom_ids must not be processed."""
    from app.cogs.registration_cog import RegistrationCog
    bot = MagicMock()
    cog = RegistrationCog(bot)
    interaction = make_button_interaction("fcm:v1:locker:open:_:abc123")

    with patch("app.onboarding.custom_ids.parse_onboarding_id") as mock_parse:
        await cog.on_interaction(interaction)
        mock_parse.assert_not_called()


@pytest.mark.asyncio
async def test_next_action_dispatches_to_handle_next_step():
    """A valid 'next' onboarding button should call handle_next_step."""
    from app.cogs.registration_cog import RegistrationCog
    session_id = uuid.uuid4()
    hex_id = str(session_id).replace("-", "")
    custom_id = f"fcm:v1:onboarding:next:{hex_id}:WELCOME"

    bot = MagicMock()
    cog = RegistrationCog(bot)
    interaction = make_button_interaction(custom_id, user_id=12345)

    mock_next = AsyncMock()

    with patch("app.services.onboarding_service.OnboardingService.handle_next_step", mock_next):
        await cog.on_interaction(interaction)

    mock_next.assert_awaited_once_with(
        interaction=interaction,
        session_id=session_id,
        current_step="WELCOME",
    )


@pytest.mark.asyncio
async def test_club_name_action_opens_modal():
    """A 'club_name' action should open the ClubNameModal."""
    from app.cogs.registration_cog import RegistrationCog
    session_id = uuid.uuid4()
    hex_id = str(session_id).replace("-", "")
    custom_id = f"fcm:v1:onboarding:club_name:{hex_id}:modal"

    bot = MagicMock()
    cog = RegistrationCog(bot)
    interaction = make_button_interaction(custom_id)

    modal_instance = MagicMock()
    MockModal = MagicMock(return_value=modal_instance)

    with patch("app.onboarding.modals.ClubNameModal", MockModal):
        await cog.on_interaction(interaction)

    interaction.response.send_modal.assert_awaited_once_with(modal_instance)
    MockModal.assert_called_once_with(session_id=session_id)


@pytest.mark.asyncio
async def test_legacy_short_id_fallback_resolves_correctly():
    """Verify that a legacy 8-character prefix resolves using _resolve_session_id."""
    from app.cogs.registration_cog import RegistrationCog
    session_id = uuid.uuid4()
    custom_id = "fcm:v1:onboarding:next:1ab14b87:WELCOME"

    bot = MagicMock()
    cog = RegistrationCog(bot)
    interaction = make_button_interaction(custom_id, user_id=12345)

    mock_next = AsyncMock()
    mock_resolve = AsyncMock(return_value=session_id)

    with (
        patch.object(cog, "_resolve_session_id", mock_resolve),
        patch("app.services.onboarding_service.OnboardingService.handle_next_step", mock_next)
    ):
        await cog.on_interaction(interaction)

    mock_resolve.assert_awaited_once_with(99999, 12345, "1ab14b87")
    mock_next.assert_awaited_once_with(
        interaction=interaction,
        session_id=session_id,
        current_step="WELCOME",
    )


@pytest.mark.asyncio
async def test_expired_legacy_session_sends_error_message():
    """When _resolve_session_id returns None for a legacy ID, user gets an error message."""
    from app.cogs.registration_cog import RegistrationCog
    custom_id = "fcm:v1:onboarding:next:deadbeef:WELCOME"

    bot = MagicMock()
    cog = RegistrationCog(bot)
    interaction = make_button_interaction(custom_id)

    with patch.object(cog, "_resolve_session_id", new_callable=AsyncMock, return_value=None):
        await cog.on_interaction(interaction)

    interaction.response.send_message.assert_awaited_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "expired" in msg.lower()
