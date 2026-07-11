# apps/discord_bot/embeds/onboarding_embeds.py
from __future__ import annotations
import discord
from gacha import GachaPlayer

# Brand color constants
COLOR_EMERALD = 0x00FF87  # Premium pitch green
COLOR_GOLD = 0xFFCC00     # Marquee / captain gold
COLOR_GRAY = 0x7F8C8D     # Neutral loading gray

def welcome_thread_embed(username: str) -> discord.Embed:
    """Initial onboarding thread welcome embed."""
    embed = discord.Embed(
        title="⚽ Welcome to ElevenBoss!",
        description=(
            f"Hello **{username}**! You are about to embark on your journey as a football club manager.\n\n"
            "To get started, we need to register your club and sign your first squad of players."
        ),
        color=COLOR_EMERALD
    )
    embed.add_field(
        name="📋 Registration Process",
        value=(
            "1. Click the **Begin Setup** button below.\n"
            "2. Choose your **Club Name** and **Manager Name**.\n"
            "3. Confirm your details and start scouting your first marquee signing!"
        ),
        inline=False
    )
    embed.set_footer(text="ElevenBoss Onboarding • v1.0.0")
    return embed

def club_confirmation_embed(club_name: str, manager_name: str) -> discord.Embed:
    """Club confirmation embed."""
    embed = discord.Embed(
        title="📝 Confirm Your Club Details",
        description="Please review your details before finalized registration.",
        color=COLOR_EMERALD
    )
    embed.add_field(name="🛡️ Club Name", value=f"**{club_name}**", inline=True)
    embed.add_field(name="👔 Manager Name", value=f"**{manager_name}**", inline=True)
    embed.set_footer(text="Verify details. If incorrect, select Edit.")
    return embed

def recruitment_embed(step_text: str) -> discord.Embed:
    """Recruitment animation frame embed."""
    embed = discord.Embed(
        title=" scouting Transfer Market...",
        description=f"### {step_text}",
        color=COLOR_GRAY
    )
    return embed

def marquee_reveal_embed(player: GachaPlayer) -> discord.Embed:
    """spotlight Captain card reveal embed."""
    rarity_emoji = "⭐" if player.rarity == "Rare" else "🔥"
    embed = discord.Embed(
        title=f"✨ MARQUEE SIGNING FOUND! ✨",
        description=(
            f"Congratulations! You have signed **{player.name}** as your new club Captain!\n\n"
            f"### {rarity_emoji} {player.rarity.upper()} CARD REVEAL"
        ),
        color=COLOR_GOLD
    )
    embed.add_field(name="🏃 Name", value=player.name, inline=True)
    embed.add_field(name="🎯 Position", value=player.position, inline=True)
    embed.add_field(name="📊 Rating", value=f"**{player.overall} OVR**", inline=True)
    embed.add_field(name="💼 Role", value=player.role, inline=True)
    embed.set_footer(text="Captain of your starter squad")
    return embed

def registration_complete_embed(marquee: GachaPlayer, youth_players: list[GachaPlayer], club_name: str, manager_name: str) -> list[discord.Embed]:
    """Final registration complete success embeds (returns [welcome_embed, academy_embed])."""
    # Embed 1: Captain reveal and welcome message
    embed1 = discord.Embed(
        title="🏆 Registration Successful!",
        description=(
            f"Welcome to the pitch, Manager **{manager_name}**!\n\n"
            f"You have successfully registered **{club_name}** and signed **{marquee.name}** "
            "to lead your team, alongside 10 youth academy prospects!\n\n"
            "Your starting 11 has been auto-assigned in a standard **4-4-2 formation** and is ready for match simulation."
        ),
        color=COLOR_EMERALD
    )
    rarity_emoji = "⭐" if marquee.rarity == "Rare" else "🔥"
    embed1.add_field(
        name="🎖️ Starter Captain (Marquee Signing)",
        value=(
            f"{rarity_emoji} **{marquee.name}** ({marquee.position}) — "
            f"**{marquee.overall} OVR** [{marquee.rarity}] · 💼 {marquee.role}"
        ),
        inline=False
    )
    embed1.set_footer(text="Tip: Use /match play in any server channel to play your first match!")

    # Sort youth players GK -> DEF -> MID -> FWD
    ordered_youth = sorted(
        youth_players,
        key=lambda p: ["GK", "DEF", "MID", "FWD"].index(p.position)
    )

    emoji_map = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
    youth_list = []
    for p in ordered_youth:
        emo = emoji_map.get(p.position, "🏃")
        youth_list.append(
            f"{emo} **{p.position}** - {p.name} ({p.overall} OVR) · {p.role}"
        )

    # Embed 2: Youth academy prospects
    embed2 = discord.Embed(
        title="🌱 Youth Academy Prospects",
        description="\n".join(youth_list),
        color=COLOR_GRAY
    )
    
    return [embed1, embed2]
