# apps/discord_bot/cogs/player_cog.py
from __future__ import annotations
import logging
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from player_engine import GameConfig, calculate_level, calculate_contract_renewal_cost
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

EVOLUTION_TRACKS = {
    "pace_boost": {
        "name": "⚡ Pace Masterclass",
        "description": "Improve your player's speed and burst.",
        "metric": "matches",
        "goal": 3,
        "reward_stat": "pac",
        "reward_val": 5
    },
    "shooting_star": {
        "name": "🎯 Shooting Star",
        "description": "Drill clinical shooting and finishing.",
        "metric": "matches",
        "goal": 3,
        "reward_stat": "sho",
        "reward_val": 5
    },
    "def_wall": {
        "name": "🧱 Defensive Wall",
        "description": "Construct a rock-solid defensive foundation.",
        "metric": "matches",
        "goal": 3,
        "reward_stat": "def",
        "reward_val": 5
    }
}

async def player_id_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    try:
        db = await get_client()
        res = await db.table("player_cards").select("id, name, overall").eq("owner_id", interaction.user.id).execute()
        cards = res.data or []
        choices = [
            app_commands.Choice(name=f"{c['name']} ({c['overall']} OVR)", value=c["id"])
            for c in cards if current.lower() in c["name"].lower()
        ]
        return choices[:25]
    except Exception:
        return []

def get_xp_progress(total_xp: int) -> tuple[int, int, int]:
    """Returns (current_level, current_xp_in_level, xp_needed_for_next_level)."""
    lvl = 1
    accumulated_xp = 0
    while True:
        needed = int(100 * (1.12 ** (lvl - 1)))
        if total_xp >= accumulated_xp + needed:
            accumulated_xp += needed
            lvl += 1
        else:
            break
    current_xp = total_xp - accumulated_xp
    needed = int(100 * (1.12 ** (lvl - 1)))
    return lvl, current_xp, needed

def make_xp_bar(current: int, needed: int) -> str:
    total_bars = 10
    filled = min(total_bars, int((current / needed) * total_bars))
    empty = total_bars - filled
    return f"`[{'█' * filled}{'░' * empty}]` ({current}/{needed} XP)"

class AttributeButton(discord.ui.Button):
    def __init__(self, attribute_name: str, label: str, card_id: str, owner_id: int) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label=label)
        self.attribute_name = attribute_name
        self.card_id = card_id
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            db = await get_client()
            
            # Fetch card
            card_res = await db.table("player_cards").select("*").eq("id", self.card_id).maybe_single().execute()
            card = card_res.data
            if not card or card["skill_points"] <= 0:
                await interaction.followup.send(embed=error_embed("No skill points available."), ephemeral=True)
                return

            new_val = card[self.attribute_name] + 1
            if new_val > 99:
                await interaction.followup.send(embed=error_embed("Attribute is already capped at 99."), ephemeral=True)
                return

            new_points = card["skill_points"] - 1

            # Update DB
            await db.table("player_cards").update({
                self.attribute_name: new_val,
                "skill_points": new_points
            }).eq("id", self.card_id).execute()

            # Refresh view
            view: AttributeAllocationView = self.view
            view.skill_points = new_points
            view.attributes[self.attribute_name] = new_val
            view.update_buttons()

            embed = discord.Embed(
                title=f"📊 Allocate Skill Points: {card['name']}",
                description=(
                    f"Points Remaining: **{new_points}**\n\n"
                    f"⚡ **PAC**: {view.attributes['pac']} | "
                    f"🎯 **SHO**: {view.attributes['sho']} | "
                    f"🧠 **PAS**: {view.attributes['pas']}\n"
                    f"👟 **DRI**: {view.attributes['dri']} | "
                    f"🛡️ **DEF**: {view.attributes['def']} | "
                    f"💪 **PHY**: {view.attributes['phy']}"
                ),
                color=0x00FF87
            )
            await interaction.edit_original_response(embed=embed, view=view)

        except Exception as e:
            logger.exception("Failed to allocate attribute point.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

class AttributeAllocationView(discord.ui.View):
    def __init__(self, card_id: str, owner_id: int, skill_points: int, attributes: dict[str, int]) -> None:
        super().__init__(timeout=180)
        self.card_id = card_id
        self.owner_id = owner_id
        self.skill_points = skill_points
        self.attributes = attributes
        self.setup_buttons()

    def setup_buttons(self) -> None:
        self.clear_items()
        self.pac_btn = AttributeButton("pac", "PAC +1", self.card_id, self.owner_id)
        self.sho_btn = AttributeButton("sho", "SHO +1", self.card_id, self.owner_id)
        self.pas_btn = AttributeButton("pas", "PAS +1", self.card_id, self.owner_id)
        self.dri_btn = AttributeButton("dri", "DRI +1", self.card_id, self.owner_id)
        self.def_btn = AttributeButton("def", "DEF +1", self.card_id, self.owner_id)
        self.phy_btn = AttributeButton("phy", "PHY +1", self.card_id, self.owner_id)

        self.add_item(self.pac_btn)
        self.add_item(self.sho_btn)
        self.add_item(self.pas_btn)
        self.add_item(self.dri_btn)
        self.add_item(self.def_btn)
        self.add_item(self.phy_btn)
        self.update_buttons()

    def update_buttons(self) -> None:
        disabled = self.skill_points <= 0
        for item in self.children:
            if isinstance(item, AttributeButton):
                item.disabled = disabled or (self.attributes[item.attribute_name] >= 99)

class EvolutionSelect(discord.ui.Select):
    def __init__(self, card_id: str, owner_id: int) -> None:
        self.card_id = card_id
        self.owner_id = owner_id
        options = []
        for key, value in EVOLUTION_TRACKS.items():
            options.append(
                discord.SelectOption(
                    label=value["name"],
                    description=f"{value['description']} Goal: {value['goal']} {value['metric']}",
                    value=key
                )
            )
        super().__init__(placeholder="Select an evolution path...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            db = await get_client()
            evo_key = self.values[0]
            track = EVOLUTION_TRACKS[evo_key]

            # Verify if this player card is already in an evolution
            existing = await db.table("active_evolutions").select("*").eq("card_id", self.card_id).execute()
            if existing.data:
                await interaction.followup.send(embed=error_embed("This card is already undergoing an evolution track!"), ephemeral=True)
                return

            # Insert evolution
            await db.table("active_evolutions").insert({
                "card_id": self.card_id,
                "evolution_id": evo_key,
                "target_metric": track["metric"],
                "target_goal": track["goal"],
                "current_progress": 0
            }).execute()

            # Disable select
            self.disabled = True
            await interaction.edit_original_response(view=self.view)

            await interaction.followup.send(
                embed=success_embed(
                    f"💪 **Evolution Started!**\n\n"
                    f"You have registered this player for the **{track['name']}** track.\n"
                    f"• Objective: Play **{track['goal']} matches** with this player in your squad."
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.exception("Failed to start evolution.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

class EvolutionSelectionView(discord.ui.View):
    def __init__(self, card_id: str, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.add_item(EvolutionSelect(card_id, owner_id))

class PlayerProfileView(discord.ui.View):
    def __init__(self, card_id: str, owner_id: int, card_name: str, has_evo: bool, can_claim: bool, renewal_cost: int) -> None:
        super().__init__(timeout=180)
        self.card_id = card_id
        self.owner_id = owner_id
        self.card_name = card_name

        # Renew Contract Button
        self.renew_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=f"Renew Contract (🪙 {renewal_cost})",
            custom_id="renew_contract_profile"
        )
        self.renew_btn.callback = self.renew_callback
        self.add_item(self.renew_btn)

        # Evolution Button
        if can_claim:
            self.evo_btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Claim Evolution Reward!",
                custom_id="claim_evo_profile"
            )
            self.evo_btn.callback = self.claim_evo_callback
            self.add_item(self.evo_btn)
        elif not has_evo:
            self.evo_btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Start Evolution",
                custom_id="start_evo_profile"
            )
            self.evo_btn.callback = self.start_evo_callback
            self.add_item(self.evo_btn)

    async def renew_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # Fetch card OVR
            card_res = await db.table("player_cards").select("overall").eq("id", self.card_id).maybe_single().execute()
            ovr = card_res.data["overall"] if card_res.data else 50
            cost = calculate_contract_renewal_cost(ovr, GameConfig())

            # Call RPC
            res = await db.rpc("renew_contract", {
                "p_club_id": self.owner_id,
                "p_card_id": self.card_id,
                "p_cost": cost,
                "p_extension_days": 7
            }).execute()

            if res.data:
                await interaction.followup.send(
                    embed=success_embed(
                        f"📝 **Contract Renewed!**\n\n"
                        f"Extended **{self.card_name}'s** contract by **7 days**.\n"
                        f"• Cost: `🪙 {cost} coins`"
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(embed=error_embed("Contract renewal failed."), ephemeral=True)

        except Exception as e:
            logger.exception("Failed to renew contract.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    async def start_evo_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another player.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🧬 Choose Evolution Path",
            description="Select an Evolution objective track to start training this player card:",
            color=0x00FF87
        )
        view = EvolutionSelectionView(self.card_id, self.owner_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def claim_evo_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # Fetch active evolution
            evo_res = await db.table("active_evolutions").select("*").eq("card_id", self.card_id).maybe_single().execute()
            evo = evo_res.data
            if not evo or evo["current_progress"] < evo["target_goal"]:
                await interaction.followup.send(embed=error_embed("Evolution is not complete yet."), ephemeral=True)
                return

            track = EVOLUTION_TRACKS[evo["evolution_id"]]

            # Fetch card
            card_res = await db.table("player_cards").select("*").eq("id", self.card_id).maybe_single().execute()
            card = card_res.data

            new_stat_val = card[track["reward_stat"]] + track["reward_val"]
            new_overall = card["overall"] + 1

            # Update DB
            await db.table("player_cards").update({
                track["reward_stat"]: new_stat_val,
                "overall": new_overall
            }).eq("id", self.card_id).execute()

            # Delete Evolution track
            await db.table("active_evolutions").delete().eq("id", evo["id"]).execute()

            # Disable button
            self.evo_btn.disabled = True
            await interaction.edit_original_response(view=self)

            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Completed!**\n\n"
                    f"**{self.card_name}** achieved the evolution goals!\n"
                    f"• Reward: `+{track['reward_val']} {track['reward_stat'].upper()}`\n"
                    f"• Overall Rating: `{card['overall']} ➔ {new_overall} OVR`"
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.exception("Failed to claim evolution rewards.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="player-profile", description="View exhaustive attributes, contracts, and progression for a player.")
    @app_commands.check(ensure_registered)
    @app_commands.autocomplete(player_id=player_id_autocomplete)
    async def player_profile(self, interaction: discord.Interaction, player_id: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player card details
            card_res = await db.table("player_cards").select("*").eq("id", player_id).maybe_single().execute()
            card = card_res.data
            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
                return

            if card["owner_id"] != interaction.user.id:
                await interaction.followup.send(embed=error_embed("You do not own this player card."), ephemeral=True)
                return

            # 2. Fetch playstyles
            ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", player_id).execute()
            playstyles = [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []
            playstyles_str = ", ".join(playstyles) if playstyles else "None"

            # 3. Fetch active evolution track
            evo_res = await db.table("active_evolutions").select("*").eq("card_id", player_id).maybe_single().execute()
            evo = evo_res.data
            
            has_evo = evo is not None
            can_claim = has_evo and evo["current_progress"] >= evo["target_goal"]

            # XP progress bar
            level, curr_xp, needed_xp = get_xp_progress(card.get("xp", 0))
            xp_bar = make_xp_bar(curr_xp, needed_xp)

            # Contract expiry days
            now = datetime.datetime.now(datetime.timezone.utc)
            expiry_str = card.get("contract_expires_at")
            if expiry_str:
                expiry = datetime.datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                days_left = (expiry - now).days
                days_left = max(0, days_left)
                contract_val = f"⏳ `{days_left} Days` (Expires <t:{int(expiry.timestamp())}:D>)"
            else:
                contract_val = "❌ `No Active Contract`"

            renewal_cost = calculate_contract_renewal_cost(card["overall"], GameConfig())

            embed = discord.Embed(
                title=f" Roster Profile: {card['name']}",
                description=f"Level **{level}** {card['rarity']} Player Card (OVR **{card['overall']}**)",
                color=0x00FF87
            )
            embed.add_field(name="📋 Role Style", value=card.get("role", "Balanced"), inline=True)
            embed.add_field(name="🎂 Age / Potential", value=f"👴 {card.get('age', 25)} yrs / 📊 {card.get('potential', 85)} POT", inline=True)
            embed.add_field(name=" Morale Rating", value=f" Morale **{card.get('morale', 80)}/100**", inline=True)
            embed.add_field(name=" Level & Experience Progression", value=xp_bar, inline=False)
            
            # Attributes
            embed.add_field(
                name="📈 Player Skill Attributes",
                value=(
                    f"⚡ **PAC**: `{card.get('pac', 50)}` | "
                    f"🎯 **SHO**: `{card.get('sho', 50)}` | "
                    f"🧠 **PAS**: `{card.get('pas', 50)}`\n"
                    f"👟 **DRI**: `{card.get('dri', 50)}` | "
                    f"🛡️ **DEF**: `{card.get('def', 50)}` | "
                    f"💪 **PHY**: `{card.get('phy', 50)}`"
                ),
                inline=False
            )
            embed.add_field(name="✨ PlayStyles", value=playstyles_str, inline=True)
            embed.add_field(name="📄 Contract Status", value=contract_val, inline=False)
            embed.add_field(name="⭐ Skill Points Available", value=f"**{card.get('skill_points', 0)}** (Spend via `/player-level-up`)", inline=False)

            if has_evo:
                track = EVOLUTION_TRACKS[evo["evolution_id"]]
                progress_str = f"📈 **Evolution Track**: {track['name']} ({evo['current_progress']}/{evo['target_goal']} matches)"
                embed.add_field(name="🧬 Ongoing Evolution Track", value=progress_str, inline=False)

            view = PlayerProfileView(player_id, interaction.user.id, card["name"], has_evo, can_claim, renewal_cost)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load player profile.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    @app_commands.command(name="player-level-up", description="Spend available skill points to allocate +1 rating to attributes.")
    @app_commands.check(ensure_registered)
    @app_commands.autocomplete(player_id=player_id_autocomplete)
    async def player_level_up(self, interaction: discord.Interaction, player_id: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player card details
            card_res = await db.table("player_cards").select("*").eq("id", player_id).maybe_single().execute()
            card = card_res.data
            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
                return

            if card["owner_id"] != interaction.user.id:
                await interaction.followup.send(embed=error_embed("You do not own this player card."), ephemeral=True)
                return

            pts = card.get("skill_points", 0)
            if pts <= 0:
                await interaction.followup.send(
                    embed=error_embed(f"You have **0 skill points** available for **{card['name']}**."),
                    ephemeral=True
                )
                return

            # Display allocation panel
            embed = discord.Embed(
                title=f"📊 Allocate Skill Points: {card['name']}",
                description=(
                    f"Points Remaining: **{pts}**\n\n"
                    f"⚡ **PAC**: {card.get('pac', 50)} | "
                    f"🎯 **SHO**: {card.get('sho', 50)} | "
                    f"🧠 **PAS**: {card.get('pas', 50)}\n"
                    f"👟 **DRI**: {card.get('dri', 50)} | "
                    f"🛡️ **DEF**: {card.get('def', 50)} | "
                    f"💪 **PHY**: {card.get('phy', 50)}"
                ),
                color=0x00FF87
            )

            attrs = {
                "pac": card.get("pac", 50),
                "sho": card.get("sho", 50),
                "pas": card.get("pas", 50),
                "dri": card.get("dri", 50),
                "def": card.get("def", 50),
                "phy": card.get("phy", 50)
            }
            view = AttributeAllocationView(player_id, interaction.user.id, pts, attrs)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to start level up view.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    @app_commands.command(name="evolution-start", description="Register a player card for an Evolution track.")
    @app_commands.check(ensure_registered)
    @app_commands.autocomplete(player_id=player_id_autocomplete)
    async def evolution_start(self, interaction: discord.Interaction, player_id: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player card details
            card_res = await db.table("player_cards").select("*").eq("id", player_id).maybe_single().execute()
            card = card_res.data
            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
                return

            if card["owner_id"] != interaction.user.id:
                await interaction.followup.send(embed=error_embed("You do not own this player card."), ephemeral=True)
                return

            # Verify active evolution
            evo_res = await db.table("active_evolutions").select("*").eq("card_id", player_id).execute()
            if evo_res.data:
                await interaction.followup.send(embed=error_embed("This card is already undergoing an evolution track!"), ephemeral=True)
                return

            embed = discord.Embed(
                title="🧬 Evolution Track Selection",
                description=f"Select an evolution path to start training **{card['name']}**:",
                color=0x00FF87
            )
            view = EvolutionSelectionView(player_id, interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to start evolution selection view.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlayerCog(bot))
