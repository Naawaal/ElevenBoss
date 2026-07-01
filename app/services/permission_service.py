# app/services/permission_service.py

import logging
import discord
from app.db.session import get_session
from app.repositories.guild_config_repository import get_or_create_guild_config

logger = logging.getLogger("app.services.permission_service")

# Global reference to Bot to discover guilds in DM context
bot = None

async def is_discord_admin(member_or_interaction) -> bool:
    """
    Checks if a user has Discord Administrator permissions.
    """
    if hasattr(member_or_interaction, "user"):
        member = member_or_interaction.user
    else:
        member = member_or_interaction
        
    if not member or not hasattr(member, "guild_permissions"):
        return False
    return member.guild_permissions.administrator

async def has_elevenboss_admin_role(guild_id: int, member) -> bool:
    """
    Checks if a member has the configured ElevenBoss admin role.
    """
    if not member or not hasattr(member, "roles"):
        return False
        
    try:
        async with get_session() as session:
            config = await get_or_create_guild_config(session, guild_id)
            if not config or not config.admin_role_id:
                return False
            role_id_str = str(config.admin_role_id)
            return any(str(r.id) == role_id_str for r in member.roles)
    except Exception as e:
        logger.error(f"Error checking ElevenBoss admin role for guild_id={guild_id}: {e}", exc_info=e)
        return False

async def can_manage_settings(guild_id: int, member) -> bool:
    """
    Check if user is a Discord admin or has the ElevenBoss admin role.
    """
    is_admin = await is_discord_admin(member)
    if is_admin:
        return True
    return await has_elevenboss_admin_role(guild_id, member)

async def can_manage_admin_role(guild_id: int, user_id_or_member) -> bool:
    """
    Only Discord Administrators can configure or change the ElevenBoss admin role.
    Supports both user_id (int/str) and discord.Member objects.
    """
    if isinstance(user_id_or_member, (int, str)):
        if bot is None:
            return False
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
        member = guild.get_member(int(user_id_or_member))
        if not member:
            try:
                member = await guild.fetch_member(int(user_id_or_member))
            except Exception:
                return False
    else:
        member = user_id_or_member
        
    return await is_discord_admin(member)

async def can_run_admin_action(guild_id: int, user_id_or_member) -> bool:
    """
    Either Discord Administrator or configured ElevenBoss admin role.
    Supports both user_id (int/str) and discord.Member objects.
    """
    return await can_manage_guild_settings(guild_id, user_id_or_member)

async def get_manageable_guilds(user_id: int) -> list[discord.Guild]:
    """
    Returns a list of guilds the user is authorized to configure.
    """
    if bot is None:
        logger.warning("bot reference not set in permission_service; returning empty guild list.")
        return []
        
    manageable = []
    for guild in bot.guilds:
        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except Exception:
                continue
                
        if member:
            is_admin = await is_discord_admin(member)
            has_role = await has_elevenboss_admin_role(int(guild.id), member)
            if is_admin or has_role:
                manageable.append(guild)
                
    return manageable

async def can_manage_guild_settings(guild_id: int, user_id_or_member) -> bool:
    """
    Revalidates permissions for a specific guild and user.
    """
    if isinstance(user_id_or_member, (int, str)):
        if bot is None:
            return False
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
        member = guild.get_member(int(user_id_or_member))
        if not member:
            try:
                member = await guild.fetch_member(int(user_id_or_member))
            except Exception:
                return False
    else:
        member = user_id_or_member
        
    return await can_manage_settings(int(guild_id), member)
