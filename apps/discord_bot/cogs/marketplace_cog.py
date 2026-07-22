# apps/discord_bot/cogs/marketplace_cog.py
from __future__ import annotations
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.core.card_payload import effective_card_age
from economy import GameConfig, generate_agent_offer
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.middleware.match_lock import assert_not_in_match
from apps.discord_bot.core.economy_rpc import wages_market_block_message
from apps.discord_bot.views.marketplace_transfer import (
    active_listing_count,
    listed_card_ids,
    show_my_listings,
    show_search_market,
    transfer_market_enabled,
)

logger = logging.getLogger(__name__)


async def show_marketplace_hub(interaction: discord.Interaction, owner_id: int):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    from apps.discord_bot.core import perf_signals

    with perf_signals.hub_timer("marketplace"):
        db = await get_client()
        player_res, enabled = await asyncio.gather(
            db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute(),
            transfer_market_enabled(db),
        )
        player = player_res.data
        active_count, slot_cap = (
            await active_listing_count(db, owner_id) if enabled else (0, 5)
        )
        tokens = player.get("tokens", 0)
        listing_status = f"`{active_count} / {slot_cap}` slots filled" if enabled else "unavailable"
        embed = discord.Embed(
            title="🏪 Global Transfer Market",
            description=(
                f"Welcome to the ElevenBoss Marketplace, Manager **{player['manager_name']}**!\n\n"
                f"💰 **Your Balance**: `🪙 {player['coins']:,} coins` | `🎟️ {tokens:,} tokens`\n"
                f"📋 **Active Listings**: {listing_status}"
            ),
            color=0x00FF87
        )
        view = MarketplaceHubView(owner_id, transfer_enabled=enabled)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

class MarketplaceHubView(discord.ui.View):
    def __init__(self, owner_id: int, *, transfer_enabled: bool = False) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.transfer_enabled = transfer_enabled
        self.sell_btn.label = "💰 Sell to Agent"
        self.listings_btn.label = "📋 My Listings"
        self.listings_btn.disabled = not transfer_enabled

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This dashboard is managed by another club.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, label="💰 Sell to Agent", custom_id="market_sell")
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_sell_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🔍 Search Market", custom_id="market_search")
    async def search_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.transfer_enabled:
            await show_search_market(interaction, self.owner_id)
        else:
            await show_scouting_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="📋 My Listings", custom_id="market_listings", disabled=True)
    async def listings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_my_listings(interaction, self.owner_id)


# --- SELL PLAYER SUB-VIEW FLOW ---

async def show_sell_menu(interaction: discord.Interaction, owner_id: int):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    db = await get_client()

    roster_res, assignments_res, evo_res, training_res, listing_card_ids = await asyncio.gather(
        db.table("player_cards")
        .select("*")
        .eq("owner_id", owner_id)
        .order("overall", desc=True)
        .execute(),
        db.table("squad_assignments")
        .select("player_card_id")
        .eq("discord_id", owner_id)
        .execute(),
        db.table("active_evolutions")
        .select("card_id")
        .eq("owner_id", owner_id)
        .eq("status", "active")
        .execute(),
        db.table("active_training").select("card_id").execute(),
        listed_card_ids(db, owner_id),
    )
    roster = roster_res.data or []

    if not roster:
        embed = discord.Embed(title="🤝 Sell Roster Player", description="You have no players in your roster.", color=0x00FF87)
        view = SellPlayerSubView(owner_id, [], None, 0)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
        return

    starting_card_ids = {a["player_card_id"] for a in (assignments_res.data or [])}
    evo_card_ids = {e["card_id"] for e in (evo_res.data or [])}
    training_card_ids = {
        t["card_id"] for t in (training_res.data or [])
        if t.get("card_id")
    }

    # 4. Filter eligible players (exclude starting 11, evolutions, active training)
    eligible_players = [
        p for p in roster
        if not p.get("is_retired")
        and not p.get("in_academy")
        and p["id"] not in starting_card_ids
        and p["id"] not in evo_card_ids
        and p["id"] not in training_card_ids
        and str(p["id"]) not in listing_card_ids
    ]

    embed = discord.Embed(
        title="🤝 Sell Player to Agent",
        description=(
            "Select a player card from your roster below to receive a purchase valuation from transfer agents.\n"
            "*(Max **10** agent sales per day.)*\n\n"
            "*(Listed, starting XI, training, and evolving players cannot be sold.)*"
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
        card_age = effective_card_age(selected_player)
        offer = generate_agent_offer(
            selected_player["overall"],
            selected_player["rarity"],
            config,
            age=card_age,
            potential=selected_player.get("potential"),
        )

        embed = discord.Embed(
            title="🤝 Transfer Agent Offer",
            description=(
                f"An agent has made an offer to purchase **{selected_player['name']}**.\n\n"
                f"**Position**: {selected_player['position']}\n"
                f"**Rating**: **{selected_player['overall']} OVR** · **{card_age} yrs**\n"
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
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            if self.selected_card.get("injury_tier") or self.selected_card.get("in_hospital"):
                await interaction.followup.send(
                    embed=error_embed("Injured / hospitalized players cannot be sold to an agent."),
                    ephemeral=True,
                )
                return

            res = await db.rpc("process_agent_sale", {
                "p_club_id": self.owner_id,
                "p_card_id": self.selected_card["id"],
            }).execute()

            sale_value = res.data if res.data is not None else 0
            if sale_value:
                await interaction.followup.send(
                    embed=success_embed(
                        f"🤝 **Agent Sale Complete!**\n\n"
                        f"Sold **{self.selected_card['name']}** to the transfer agent for **🪙 {sale_value:,} coins**."
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


# --- SCOUTING POOL / SEARCH MARKET (Phase D) ---

async def show_scouting_menu(interaction: discord.Interaction, owner_id: int) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    db = await get_client()
    pool_res = await (
        db.table("scouting_pool_players")
        .select("*")
        .is_("claimed_by", "null")
        .order("overall", desc=True)
        .limit(25)
        .execute()
    )
    listings = pool_res.data or []

    embed = discord.Embed(
        title="🔍 Scouting Market",
        description=(
            "Youth regens listed when veteran players retire from the league.\n"
            "Select a prospect below to review and sign them to your roster.\n\n"
            + (f"**{len(listings)}** available listing(s)." if listings else "*No listings right now — check back after season aging.*")
        ),
        color=0x00FF87,
    )
    view = ScoutingSubView(owner_id, listings, None)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class ScoutingSubView(discord.ui.View):
    def __init__(self, owner_id: int, listings: list[dict], selected: dict | None) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.listings = listings
        self.selected = selected

        if listings:
            options = []
            for row in listings[:25]:
                options.append(
                    discord.SelectOption(
                        label=row["name"][:100],
                        description=f"{row['overall']} OVR · {row['position']} · 🪙 {int(row['list_price']):,}",
                        value=row["id"],
                        default=(selected and row["id"] == selected["id"]),
                    )
                )
            sel = discord.ui.Select(placeholder="Choose prospect to sign...", options=options, row=0)
            sel.callback = self.select_callback
            self.add_item(sel)

        if selected:
            btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Sign Player (🪙 {int(selected['list_price']):,})",
                row=1,
            )
            btn.callback = self.confirm_callback
            self.add_item(btn)

        back = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Market", row=2)
        back.callback = self.back_callback
        self.add_item(back)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_marketplace_hub(interaction, self.owner_id)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        pool_id = interaction.data["values"][0]
        picked = next((r for r in self.listings if r["id"] == pool_id), None)
        if not picked:
            return
        embed = discord.Embed(
            title=f"🔍 {picked['name']}",
            description=(
                f"**Position:** {picked['position']}\n"
                f"**Rating:** {picked['overall']} OVR · **{picked['age']} yrs**\n"
                f"**Potential:** {picked['potential']} POT · {picked['rarity']}\n\n"
                f"### Signing fee: 🪙 **{int(picked['list_price']):,} coins**"
            ),
            color=0x00FF87,
        )
        await interaction.edit_original_response(embed=embed, view=ScoutingSubView(self.owner_id, self.listings, picked))

    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not self.selected:
            return
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            wage_msg = await wages_market_block_message(db, self.owner_id)
            if wage_msg:
                await interaction.followup.send(embed=error_embed(wage_msg), ephemeral=True)
                return

            price = int(self.selected["list_price"])
            res = await db.rpc("purchase_scouting_player", {
                "p_buyer_id": self.owner_id,
                "p_pool_id": self.selected["id"],
                "p_expected_price": price,
            }).execute()
            data = res.data or {}
            await interaction.followup.send(
                embed=success_embed(
                    f"Signed **{data.get('player_name', self.selected['name'])}** "
                    f"for **🪙 {data.get('coins_spent', price):,}** coins."
                ),
                ephemeral=True,
            )
            await show_scouting_menu(interaction, self.owner_id)
        except Exception as exc:
            logger.exception("Scouting purchase failed.")
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)


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
            await show_marketplace_hub(interaction, interaction.user.id)

        except Exception as e:
            logger.exception("Failed to load Marketplace.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MarketplaceCog(bot))
