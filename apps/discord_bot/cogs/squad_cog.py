# apps/discord_bot/cogs/squad_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.embeds.squad_embeds import get_slot_position, starting_11_embed, roster_embed

logger = logging.getLogger(__name__)

class RosterPaginationView(discord.ui.View):
    def __init__(self, interaction_user_id: int, cards: list[dict], per_page: int = 8) -> None:
        super().__init__(timeout=180)
        self.user_id = interaction_user_id
        self.cards = cards
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(cards) + per_page - 1) // per_page)
        self.update_buttons()

    def update_buttons(self) -> None:
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page >= self.total_pages - 1

    def get_embed(self) -> discord.Embed:
        return roster_embed(self.cards, self.current_page, self.total_pages)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class FormationSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="4-4-2", description="Standard balanced formation", emoji="⚽"),
            discord.SelectOption(label="4-3-3", description="Attacking formation with wingers", emoji="⚔️"),
            discord.SelectOption(label="3-5-2", description="Midfield dominance formation", emoji="🛡️"),
            discord.SelectOption(label="4-2-3-1", description="Modern tactical formation", emoji="🧠"),
            discord.SelectOption(label="5-3-2", description="Defensive counter-attacking formation", emoji="🚌"),
        ]
        super().__init__(placeholder="Select a formation...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        formation = self.values[0]
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            await db.table("squads").update({"formation": formation}).eq("discord_id", interaction.user.id).execute()
            await interaction.followup.send(
                embed=success_embed(f"Your active formation has been set to **{formation}**."),
                ephemeral=True
            )
        except Exception as e:
            logger.exception("Failed to set formation via dropdown.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred: {str(e)}"),
                ephemeral=True
            )


class FormationSelectView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.add_item(FormationSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True


class SlotSelect(discord.ui.Select):
    def __init__(self, formation: str) -> None:
        self.formation = formation
        emoji_map = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
        options = []
        for slot in range(1, 12):
            pos = get_slot_position(formation, slot)
            options.append(
                discord.SelectOption(
                    label=f"Slot {slot} ({pos})",
                    value=str(slot),
                    emoji=emoji_map.get(pos, "🏃")
                )
            )
        super().__init__(placeholder="Choose a slot to assign...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PlayerAssignView = self.view
        selected_slot = int(self.values[0])
        view.selected_slot = selected_slot
        
        # Defer update
        await interaction.response.defer()
        
        # Fetch players matching this position
        required_pos = get_slot_position(self.formation, selected_slot)
        db = await get_client()
        res = await db.table("player_cards").select("*").eq("owner_id", interaction.user.id).eq("position", required_pos).order("overall", desc=True).execute()
        players = res.data or []
        
        # Filter to top 25
        players = players[:25]
        
        # Update PlayerSelect options
        player_select: PlayerSelect = view.player_select
        if not players:
            player_select.options = [discord.SelectOption(label="No available players", value="none")]
            player_select.disabled = True
            player_select.placeholder = f"No {required_pos} players available"
        else:
            options = []
            rarity_emojis = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
            for p in players:
                emoji = rarity_emojis.get(p["rarity"], "⚪")
                options.append(
                    discord.SelectOption(
                        label=p["name"],
                        description=f"{p['overall']} OVR | {p['rarity']}",
                        value=p["id"],
                        emoji=emoji
                    )
                )
            player_select.options = options
            player_select.disabled = False
            player_select.placeholder = f"Assign {required_pos} to Slot {selected_slot}..."
            
        # Edit response to show updated view
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="⚙️ Configure Squad Slot",
                description=f"Selected **Slot {selected_slot} ({required_pos})**. Now select a player card from the dropdown below:",
                color=0x00FF87
            ),
            view=view
        )


class PlayerSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [discord.SelectOption(label="Select a slot first", value="placeholder")]
        super().__init__(placeholder="Select a player...", min_values=1, max_values=1, options=options, disabled=True)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PlayerAssignView = self.view
        selected_player_id = self.values[0]
        selected_slot = view.selected_slot
        
        if selected_player_id in ["placeholder", "none"] or selected_slot is None:
            await interaction.response.send_message("Invalid selection.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            
            # Fetch card details to verify ownership
            card_res = await db.table("player_cards").select("*").eq("id", selected_player_id).maybe_single().execute()
            card = card_res.data if card_res else None
            
            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found in roster."), ephemeral=True)
                return
                
            # Clean conflict: if this card is already assigned to a different slot, remove it first
            await db.table("squad_assignments").delete().eq("discord_id", interaction.user.id).eq("player_card_id", selected_player_id).execute()
            
            # Upsert assignment
            await db.table("squad_assignments").upsert({
                "discord_id": interaction.user.id,
                "position_slot": selected_slot,
                "player_card_id": selected_player_id
            }).execute()
            
            await interaction.followup.send(
                embed=success_embed(f"**{card['name']}** ({card['position']}) has been assigned to **Slot {selected_slot}**."),
                ephemeral=True
            )
            
            # Reset player select view to disabled placeholder state
            self.disabled = True
            self.options = [discord.SelectOption(label="Select a slot first", value="placeholder")]
            self.placeholder = "Select a player..."
            
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="⚙️ Configure Squad Slot",
                    description="Player assigned successfully! Select another slot from the dropdown below to continue:",
                    color=0x00FF87
                ),
                view=view
            )
            
        except Exception as e:
            logger.exception("Failed to assign player via select.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred: {str(e)}"),
                ephemeral=True
            )


class PlayerAssignView(discord.ui.View):
    def __init__(self, owner_id: int, formation: str) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.selected_slot: int | None = None
        
        self.slot_select = SlotSelect(formation)
        self.player_select = PlayerSelect()
        
        self.add_item(self.slot_select)
        self.add_item(self.player_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True


class SquadCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="squad-view", description="View your current starting 11 and active formation.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def squad_view(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            # Fetch squad metadata
            squad_res = await db.table("squads").select("formation").eq("discord_id", interaction.user.id).maybe_single().execute()
            formation = squad_res.data["formation"] if (squad_res and squad_res.data and "formation" in squad_res.data) else "4-4-2"

            # Fetch squad assignments joined with player cards
            assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", interaction.user.id).execute()
            assignments = {a["position_slot"]: a["player_cards"] for a in assignments_res.data if a.get("player_cards")}

            # Build squad starting 11 embed
            embed = starting_11_embed(formation, assignments)

            # Fetch full roster
            roster_res = await db.table("player_cards").select("*").eq("owner_id", interaction.user.id).order("overall", desc=True).execute()
            cards = roster_res.data or []

            # Send starter embed with roster pagination view
            view = RosterPaginationView(interaction.user.id, cards)
            
            # Send starting 11 first, and then the roster
            await interaction.followup.send(embed=embed, ephemeral=True)
            roster_msg = await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)
            view.message = roster_msg

        except Exception as e:
            logger.exception("Failed to load squad view.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while loading squad: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="squad-set-formation", description="Set your starting formation using an interactive dropdown.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def squad_set_formation(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚽ Set Team Formation",
                    description="Choose your starting formation from the dropdown menu below:",
                    color=0x00FF87
                ),
                view=FormationSelectView(interaction.user.id),
                ephemeral=True
            )
        except Exception as e:
            logger.exception("Failed to start formation select view.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="squad-set-player", description="Assign a roster player to a starting 11 slot using interactive dropdowns.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def squad_set_player(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            # Fetch active formation
            squad_res = await db.table("squads").select("formation").eq("discord_id", interaction.user.id).maybe_single().execute()
            formation = squad_res.data["formation"] if (squad_res and squad_res.data) else "4-4-2"

            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚙️ Configure Squad Slot",
                    description="Select the **Slot (1-11)** you wish to assign, then choose a player card from your roster:",
                    color=0x00FF87
                ),
                view=PlayerAssignView(interaction.user.id, formation),
                ephemeral=True
            )
        except Exception as e:
            logger.exception("Failed to start squad set player view.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred: {str(e)}"),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SquadCog(bot))
