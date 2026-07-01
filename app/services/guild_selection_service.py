# app/services/guild_selection_service.py

from dataclasses import dataclass
import discord
from app.services.permission_service import get_manageable_guilds, is_discord_admin

@dataclass
class ManageableGuildView:
    guild_id: int
    guild_name: str
    icon_url: str | None = None
    permission_label: str = "Admin"

class GuildSelectionService:
    @staticmethod
    async def get_manageable_guilds(user_id: int) -> list[ManageableGuildView]:
        """
        Discovers and maps manageable guilds for a specific user.
        """
        guilds = await get_manageable_guilds(user_id)
        views = []
        for guild in guilds:
            member = guild.get_member(user_id)
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    continue
            
            if member:
                is_admin = await is_discord_admin(member)
                label = "Discord Admin" if is_admin else "ElevenBoss Admin"
                icon_url = str(guild.icon.url) if guild.icon else None
                views.append(ManageableGuildView(
                    guild_id=int(guild.id),
                    guild_name=guild.name,
                    icon_url=icon_url,
                    permission_label=label
                ))
        return views
