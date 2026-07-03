import unittest
import asyncio
import discord
from unittest.mock import AsyncMock, patch, MagicMock

# Mock asyncio.get_running_loop() before importing any discord.ui components
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

import pytest
from app.cogs.club_cog import ClubCog


@pytest.mark.asyncio
@patch("app.cogs.club_cog.capture_exception")
async def test_on_interaction_expired_graceful_catch(mock_capture):
    # Setup cog instance
    bot = MagicMock()
    cog = ClubCog(bot)
    
    # Mock expired interaction triggering discord.NotFound
    interaction = MagicMock(spec=discord.Interaction)
    interaction.type = discord.InteractionType.component
    interaction.data = {"custom_id": "fcm:v1:locker:open:club:nonce123"}
    interaction.guild_id = 12345
    interaction.user.id = 111
    
    # Force defer to raise NotFound with code 10062
    not_found_err = discord.NotFound(MagicMock(), "Unknown interaction")
    not_found_err.code = 10062
    
    interaction.response.defer = AsyncMock(side_effect=not_found_err)
    
    # Execute on_interaction
    await cog.on_interaction(interaction)
    
    # Verify Sentry was NOT notified (no alert fatigue)
    mock_capture.assert_not_called()
    
    # Verify no send_error_response was called on interaction
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_not_called()
