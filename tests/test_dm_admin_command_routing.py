# tests/test_dm_admin_command_routing.py

import pytest
import discord
from unittest.mock import AsyncMock, patch, MagicMock
from app.cogs.dm_admin_cog import DMAdminCog

def test_command_decorators():
    # Verify group and subcommand structure
    cog = DMAdminCog(MagicMock())
    assert cog.admin is not None
    
    # Check that console subcommand exists
    console_cmd = None
    for cmd in cog.admin.commands:
        if cmd.name == "console":
            console_cmd = cmd
            break
            
    assert console_cmd is not None
    assert console_cmd.allowed_contexts is not None
    # Contexts are (guild, dm_channel, private_channel)
    assert not console_cmd.allowed_contexts.guild
    assert console_cmd.allowed_contexts.dm_channel
    assert console_cmd.allowed_contexts.private_channel

@pytest.mark.asyncio
@patch("app.cogs.dm_admin_cog.handle_open_admin_console")
async def test_admin_dm_only_routing_success(mock_handle):
    cog = DMAdminCog(MagicMock())
    
    # Find console command callback
    console_cmd = next(c for c in cog.admin.commands if c.name == "console")
    
    # Interaction inside DM (guild_id is None)
    mock_interaction = AsyncMock()
    mock_interaction.guild_id = None
    mock_interaction.user.id = 12345
    
    await console_cmd.callback(cog, mock_interaction)
    mock_handle.assert_called_once_with(mock_interaction.user)
