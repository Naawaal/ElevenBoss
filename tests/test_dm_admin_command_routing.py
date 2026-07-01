# tests/test_dm_admin_command_routing.py

import pytest
import discord
from unittest.mock import AsyncMock, patch, MagicMock
from app.cogs.dm_admin_cog import DMAdminCog

def test_command_decorators():
    # Verify allowed_contexts decorator properties
    cog = DMAdminCog(MagicMock())
    command = cog.admin
    
    assert command.allowed_contexts is not None
    # Contexts are (guild, dm_channel, private_channel)
    assert not command.allowed_contexts.guild
    assert command.allowed_contexts.dm_channel
    assert command.allowed_contexts.private_channel

@pytest.mark.asyncio
@patch("app.cogs.dm_admin_cog.handle_open_admin_console")
async def test_admin_dm_only_routing_success(mock_handle):
    cog = DMAdminCog(MagicMock())
    
    # Interaction inside DM (guild_id is None)
    mock_interaction = AsyncMock()
    mock_interaction.guild_id = None
    mock_interaction.user.id = 12345
    
    await cog.admin.callback(cog, mock_interaction)
    mock_handle.assert_called_once_with(mock_interaction.user)

@pytest.mark.asyncio
async def test_admin_dm_only_routing_rejected_in_guild():
    cog = DMAdminCog(MagicMock())
    
    # Interaction inside guild (guild_id set)
    mock_interaction = AsyncMock()
    mock_interaction.guild_id = 123456
    
    await cog.admin.callback(cog, mock_interaction)
    mock_interaction.response.send_message.assert_called_once()
    assert "moved to DM" in mock_interaction.response.send_message.call_args[0][0]
