# apps/discord_bot/cogs/marketplace_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from economy import GameConfig, generate_agent_offer
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

async def show_marketplace_hub(interaction: discord.Interaction, owner_id: int):
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data

    tokens = player.get("tokens", 0)
    
    embed = discord.Embed(
        title="🏪 Global Transfer Market",
        description=(
            f"Welcome to the ElevenBoss Marketplace, Manager **{player['manager_name']}**!\n\n"
            f"💰 **Your Balance**: `🪙 {player['coins']:,} coins` | `🎟️ {tokens:,} tokens`\n"
            f"📋 **Active Listings**: `0 / 5` slots filled"
        ),
        color=0x00FF87
    )
    view = MarketplaceHubView(owner_id)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)

class MarketplaceHubView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This dashboard is managed by another club.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, label="💰 Sell Player", custom_id="market_sell")
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_sell_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🔍 Search Market (Soon)", custom_id="market_search", disabled=True)
    async def search_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="📋 My Listings (Soon)", custom_id="market_listings", disabled=True)
    async def listings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


# --- SELL PLAYER SUB-VIEW FLOW ---

async def show_sell_menu(interaction: discord.Interaction, owner_id: int):
    db = await get_client()

    # 1. Fetch full roster
    roster_res = await db.table("player_cards").select("*").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    if not roster:
        embed = discord.Embed(title="🤝 Sell Roster Player", description="You have no players in your roster.", color=0x00FF87)
        view = SellPlayerSubView(owner_id, [], None, 0)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
        return

    # 2. Fetch starting 11 card ids
    assignments_res = await db.table("squad_assignments").select("player_card_id").eq("discord_id", owner_id).execute()
    starting_card_ids = {a["player_card_id"] for a in assignments_res.data}

    # 3. Fetch active training card ids
    training_res = await db.table("active_training").select("card_id").eq("club_id", owner_id).execute()
    training_card_ids = {t["card_id"] for t in training_res.data}

    # 4. Fetch active evolution card ids
    evo_res = await db.table("active_evolutions").select("card_id").execute()
    evo_card_ids = {e["card_id"] for e in evo_res.data}

    # 5. Filter eligible players (exclude starting 11, training, and active evolutions locks)
    eligible_players = [
        p for p in roster 
        if p["id"] not in starting_card_ids 
        and p["id"] not in training_card_ids 
        and p["id"] not in evo_card_ids
    ]

    embed = discord.Embed(
        title="🤝 Sell Roster Player",
        description=(
            "Select a player card from your roster below to receive a purchase valuation from transfer agents.\n\n"
            "*(Note: Players in starting 11, training, or active evolutions cannot be sold.)*"
        ),
        color=0x00FF87
    )
    view = SellPlayerSubView(owner_id, eligible_players, None, 0)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class SellPlayerSubView(discord.ui.View):
    def __init__(self, owner_id: int, eligible_players: list[dict], selected_card: dict | None, offer: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.eligible_players = eligible_players
        self.selected_card = selected_card
        self.offer = offer

        # 1. Player Select menu
        if eligible_players:
            player_options = []
            rarity_emojis = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
            for p in eligible_players[:25]:
                emoji = rarity_emojis.get(p["rarity"], "⚪")
                player_options.append(
                    discord.SelectOption(
                        label=p["name"],
                        description=f"{p['overall']} OVR | {p['rarity']} | {p['position']}",
                        value=p["id"],
                        emoji=emoji,
                        default=(selected_card and p["id"] == selected_card["id"])
                    )
                )
            
            player_sel = discord.ui.Select(placeholder="Choose player to sell...", options=player_options, row=0)
            player_sel.callback = self.player_select_callback
            self.add_item(player_sel)

        # 2. Confirm button if card selected
        if selected_card and offer > 0:
            confirm_btn = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label=f"Confirm Sale (🪙 {offer:,})",
                custom_id="confirm_agent_sale",
                row=1
            )
            confirm_btn.callback = self.confirm_sale_callback
            self.add_item(confirm_btn)

        # 3. Back to Market button
        back_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="⬅️ Back to Market",
            custom_id="sell_back_market",
            row=2
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction):
        await show_marketplace_hub(interaction, self.owner_id)

    async def player_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_card_id = interaction.data["values"][0]
        
        # Find player details
        selected_player = next((p for p in self.eligible_players if p["id"] == selected_card_id), None)
        if not selected_player:
            return

        config = GameConfig()
        offer = generate_agent_offer(selected_player["overall"], selected_player["rarity"], config)

        embed = discord.Embed(
            title="🤝 Transfer Agent Offer",
            description=(
                f"An agent has made an offer to purchase **{selected_player['name']}**.\n\n"
                f"**Position**: {selected_player['position']}\n"
                f"**Rating**: **{selected_player['overall']} OVR**\n"
                f"**Rarity**: {selected_player['rarity']}\n\n"
                f"### Offer: 🪙 **{offer:,} coins**\n"
                f"*Click the button below to finalize this transaction. This action is irreversible.*"
            ),
            color=0x00FF87
        )
        
        # Re-render view with Confirm button
        new_view = SellPlayerSubView(self.owner_id, self.eligible_players, selected_player, offer)
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def confirm_sale_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            res = await db.rpc("process_agent_sale", {
                "p_club_id": self.owner_id,
                "p_card_id": self.selected_card["id"],
                "p_sale_value": self.offer
            }).execute()

            if res.data:
                await interaction.followup.send(
                    embed=success_embed(
                        f"🤝 **Agent Sale Complete!**\n\n"
                        f"Sold **{self.selected_card['name']}** to the transfer agent for **🪙 {self.offer:,} coins**."
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(embed=error_embed("Sale transaction failed on the database."), ephemeral=True)

            # Re-render Sell Player View (which filters out the now sold card)
            await show_sell_menu(interaction, self.owner_id)

        except Exception as e:
            logger.exception("Failed executing process_agent_sale RPC.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)


# --- COG INTERFACE ---

class MarketplaceCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="marketplace", description="Centralized Marketplace Hub: Buy and sell players.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def marketplace(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None

            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            tokens = player.get("tokens", 0)

            embed = discord.Embed(
                title="🏪 Global Transfer Market",
                description=(
                    f"Welcome to the ElevenBoss Marketplace, Manager **{player['manager_name']}**!\n\n"
                    f"💰 **Your Balance**: `🪙 {player['coins']:,} coins` | `🎟️ {tokens:,} tokens`\n"
                    f"📋 **Active Listings**: `0 / 5` slots filled"
                ),
                color=0x00FF87
            )
            view = MarketplaceHubView(interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load Marketplace.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MarketplaceCog(bot))
