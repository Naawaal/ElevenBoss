# tests/test_permission_service.py

import pytest
import discord
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.permission_service import (
    is_discord_admin,
    has_elevenboss_admin_role,
    can_manage_settings,
    can_manage_admin_role,
    can_run_admin_action,
)
from app.models.guild_config import GuildConfig

@pytest.mark.asyncio
async def test_is_discord_admin():
    # Admin user
    mock_member = MagicMock(spec=discord.Member)
    mock_member.guild_permissions.administrator = True
    assert await is_discord_admin(mock_member)

    # Non-admin user
    mock_member_regular = MagicMock(spec=discord.Member)
    mock_member_regular.guild_permissions.administrator = False
    assert not await is_discord_admin(mock_member_regular)

@pytest.mark.asyncio
@patch("app.services.permission_service.get_session")
async def test_has_elevenboss_admin_role(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    config = GuildConfig(
        guild_id="123456",
        admin_role_id="999"
    )
    
    with patch("app.services.permission_service.get_or_create_guild_config", return_value=config):
        # Member has role
        mock_role = MagicMock()
        mock_role.id = 999
        mock_member = MagicMock(spec=discord.Member)
        mock_member.roles = [mock_role]
        
        assert await has_elevenboss_admin_role(123456, mock_member)
        
        # Member lacks role
        mock_role_other = MagicMock()
        mock_role_other.id = 888
        mock_member_other = MagicMock(spec=discord.Member)
        mock_member_other.roles = [mock_role_other]
        
        assert not await has_elevenboss_admin_role(123456, mock_member_other)

@pytest.mark.asyncio
async def test_can_manage_settings_permissions():
    # Discord admin can manage settings
    mock_member = MagicMock(spec=discord.Member)
    mock_member.guild_permissions.administrator = True
    assert await can_manage_settings(123456, mock_member)

@pytest.mark.asyncio
async def test_can_manage_admin_role_permissions():
    # Only Discord Admin can manage the admin role
    mock_admin = MagicMock(spec=discord.Member)
    mock_admin.guild_permissions.administrator = True
    assert await can_manage_admin_role(123456, mock_admin)
    
    mock_non_admin = MagicMock(spec=discord.Member)
    mock_non_admin.guild_permissions.administrator = False
    assert not await can_manage_admin_role(123456, mock_non_admin)
