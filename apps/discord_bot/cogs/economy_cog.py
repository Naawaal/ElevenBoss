# apps/discord_bot/cogs/economy_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from economy import GameConfig, calculate_weekly_wages, generate_agent_offer
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

class ConfirmSaleButton(discord.ui.Button):
    def __init__(self, card_id: str, card_name: str, offer: int, owner_id: int) -> None:
        super().__init__(style=discord.ButtonStyle.danger, label="Confirm Sale", custom_id="confirm_player_sale")
        self.card_id = card_id
        self.card_name = card_name
        self.offer = offer
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This action belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # Call RPC to process agent sale atomically
            res = await db.rpc("process_agent_sale", {
                "p_club_id": interaction.user.id,
                "p_card_id": self.card_id,
                "p_sale_value": self.offer
            }).execute()

            if res.data:
                # Disable all components in view
                view = self.view
                if view:
                    for child in view.children:
                        child.disabled = True
                    await interaction.edit_original_response(view=view)

                await interaction.followup.send(
                    embed=success_embed(
                        f"🤝 **Agent Sale Complete!**\n\n"
                        f"Sold **{self.card_name}** to the transfer agent for **🪙 {self.offer:,} coins**."
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(embed=error_embed("Sale transaction failed on the server."), ephemeral=True)

        except Exception as e:
            logger.exception("Failed to execute player agent sale RPC.")
            await interaction.followup.send(embed=error_embed(f"An error occurred during transaction: {str(e)}"), ephemeral=True)

class SellPlayerSelect(discord.ui.Select):
    def __init__(self, eligible_players: list[dict], owner_id: int) -> None:
        self.eligible_players = eligible_players
        self.owner_id = owner_id
        
        options = []
        rarity_emojis = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
        for p in eligible_players[:25]:
            emoji = rarity_emojis.get(p["rarity"], "⚪")
            options.append(
                discord.SelectOption(
                    label=p["name"],
                    description=f"{p['overall']} OVR | {p['rarity']} | {p['position']}",
                    value=p["id"],
                    emoji=emoji
                )
            )
        super().__init__(placeholder="Choose a player card to sell...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer()
        selected_card_id = self.values[0]
        
        # Find player details
        selected_player = next((p for p in self.eligible_players if p["id"] == selected_card_id), None)
        if not selected_player:
            await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
            return

        # Calculate agent offer
        config = GameConfig()
        offer = generate_agent_offer(selected_player["overall"], selected_player["rarity"], config)

        # Clear existing confirm buttons in view, if any, and add new confirm button
        view: SellPlayerView = self.view
        # Remove any existing confirm button
        confirm_btn = next((child for child in view.children if isinstance(child, ConfirmSaleButton)), None)
        if confirm_btn:
            view.remove_item(confirm_btn)
            
        # Add new confirm button
        new_confirm = ConfirmSaleButton(
            card_id=selected_card_id,
            card_name=selected_player["name"],
            offer=offer,
            owner_id=self.owner_id
        )
        view.add_item(new_confirm)

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

        await interaction.edit_original_response(embed=embed, view=view)

class SellPlayerView(discord.ui.View):
    def __init__(self, eligible_players: list[dict], owner_id: int) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.select = SellPlayerSelect(eligible_players, owner_id)
        self.add_item(self.select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="club-finances", description="View club balance ledger, wage sheets, and finance forecasts.")
    @app_commands.check(ensure_registered)
    async def club_finances(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player/club metadata
            player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None
            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            # 2. Fetch starting 11 cards
            assignments_res = await db.table("squad_assignments").select("player_cards(*)").eq("discord_id", interaction.user.id).execute()
            starting_cards = [a["player_cards"] for a in assignments_res.data if a.get("player_cards")]

            # 3. Calculate weekly wages
            config = GameConfig()
            weekly_wages = calculate_weekly_wages(starting_cards, config)

            # Get tokens safely (default to 0 if not present)
            tokens = player.get("tokens", 0)

            # 4. Render embed
            embed = discord.Embed(
                title=f"💼 Club Finances: {player['club_name']}",
                description=f"Financial statement and forecasts for Manager **{player['manager_name']}**.",
                color=0x00FF87
            )
            embed.add_field(
                name="💰 Wallet Balances",
                value=(
                    f"🪙 **Coins Balance**: `{player['coins']:,} coins`\n"
                    f"🎟️ **Tokens Balance**: `{tokens:,} tokens`"
                ),
                inline=False
            )
            embed.add_field(
                name="👔 Starting 11 Wage Bill",
                value=(
                    f"👥 **Active Starting Players**: `{len(starting_cards)}/11`\n"
                    f"📉 **Weekly Wage bill**: `🪙 {weekly_wages:,} coins / week`"
                ),
                inline=False
            )
            
            # Forecast
            net_balance_after_wage = player["coins"] - weekly_wages
            warning_text = ""
            if net_balance_after_wage < 0:
                warning_text = "\n⚠️ *Warning: Your current coin balance is insufficient to cover next week's wages.*"
                
            embed.add_field(
                name="📈 Financial Forecast",
                value=(
                    f"Estimated balance after upcoming weekly wages: `🪙 {net_balance_after_wage:,} coins`"
                    f"{warning_text}"
                ),
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to fetch club finances.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    @app_commands.command(name="sell-player", description="Sell player cards from your roster back to transfer agents for coins.")
    @app_commands.check(ensure_registered)
    async def sell_player(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch full roster
            roster_res = await db.table("player_cards").select("*").eq("owner_id", interaction.user.id).order("overall", desc=True).execute()
            roster = roster_res.data or []

            if not roster:
                await interaction.followup.send(embed=error_embed("You have no players in your roster."), ephemeral=True)
                return

            # 2. Fetch starting 11 cards
            assignments_res = await db.table("squad_assignments").select("player_card_id").eq("discord_id", interaction.user.id).execute()
            starting_card_ids = {a["player_card_id"] for a in assignments_res.data}

            # 3. Filter eligible players (not in starting 11)
            eligible_players = [p for p in roster if p["id"] not in starting_card_ids]

            if not eligible_players:
                await interaction.followup.send(
                    embed=error_embed(
                        "You have no eligible players to sell.\n"
                        "*(Note: You cannot sell player cards that are currently assigned to your starting 11 squad.)*"
                    ),
                    ephemeral=True
                )
                return

            # 4. Send interactive Sell Player View
            embed = discord.Embed(
                title="🤝 Sell Roster Player",
                description="Select a player from your roster below to receive a purchase valuation from transfer market agents:",
                color=0x00FF87
            )
            view = SellPlayerView(eligible_players, interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to start sell player view.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))
