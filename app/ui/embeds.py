import discord

def registration_success_embed(
    club_name: str,
    manager_mention: str,
    squad_size: int,
    avg_ovr: float,
    budget: int
) -> discord.Embed:
    """
    Generate a styled success embed for club registration.
    """
    embed = discord.Embed(
        title="✅ Club Registered",
        description=f"**{club_name}** has officially joined the football world.",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Manager", value=manager_mention, inline=True)
    embed.add_field(name="Squad Size", value=f"{squad_size} players", inline=True)
    embed.add_field(name="Average OVR", value=f"{avg_ovr:.1f}", inline=True)
    embed.add_field(name="Budget", value=f"£{budget:,}", inline=True)
    
    embed.add_field(
        name="Next Step", 
        value="Use `/squad` to view your players.", 
        inline=False
    )
    
    embed.set_footer(text="ElevenBoss — Football Management Simulation")
    return embed
