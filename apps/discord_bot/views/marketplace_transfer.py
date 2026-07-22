"""Discord UI flows for the opt-in P2P transfer market."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord

from apps.discord_bot.core.card_payload import effective_card_age
from apps.discord_bot.core.economy_rpc import get_game_config_int, wages_market_block_message
from apps.discord_bot.core.view_helpers import add_select_if_options
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.middleware.match_lock import assert_not_in_match
from economy import price_bounds_for_card, seller_net, validate_listing_price

logger = logging.getLogger(__name__)

POSITION_OPTIONS = ("Any", "GK", "DEF", "MID", "FWD")
BANDS = {
    "ovr": {"Any": None, "60–69": (60, 69), "70–74": (70, 74), "75–79": (75, 79), "80+": (80, 99)},
    "age": {"Any": None, "18–20": (18, 20), "21–25": (21, 25), "26–30": (26, 30), "31+": (31, 99)},
    "pot": {"Any": None, "70–79": (70, 79), "80–84": (80, 84), "85–89": (85, 89), "90+": (90, 99)},
}


def _data(response: Any) -> Any:
    """Supabase-py returns either a dict or a one-item list for JSONB RPCs."""
    value = getattr(response, "data", response)
    return value[0] if isinstance(value, list) and value else (value or {})


async def transfer_market_enabled(db: Any) -> bool:
    """Read the rollout flag on every marketplace entry."""
    try:
        result = await db.rpc("p2p_transfer_market_enabled").execute()
        value = _data(result)
        return value is True or (isinstance(value, str) and value.strip('"').lower() == "true")
    except Exception:
        logger.exception("Could not read P2P transfer-market flag.")
        return False


async def active_listing_count(db: Any, owner_id: int) -> tuple[int, int]:
    rows = await db.table("transfer_listings").select("id", count="exact").eq(
        "seller_id", owner_id
    ).eq("status", "active").execute()
    cap = await get_game_config_int(db, "transfer_listing_slot_cap", 5)
    return int(rows.count or 0), cap


async def listed_card_ids(db: Any, owner_id: int | None = None) -> set[str]:
    query = db.table("transfer_listings").select("card_id").eq("status", "active")
    if owner_id is not None:
        query = query.eq("seller_id", owner_id)
    result = await query.execute()
    return {str(row["card_id"]) for row in (result.data or [])}


def _card_text(card: dict) -> str:
    return (
        f"**{card['name']}** · {card['position']} · {card['overall']} OVR\n"
        f"Age {effective_card_age(card)} · {card.get('potential', 0)} POT"
    )


async def _eligible_listing_cards(owner_id: int) -> list[dict]:
    db = await get_client()
    cards_res, starter_rows, training_rows, evo_rows, listed = await asyncio.gather(
        db.table("player_cards")
        .select("*")
        .eq("owner_id", owner_id)
        .order("overall", desc=True)
        .execute(),
        db.table("squad_assignments")
        .select("player_card_id")
        .eq("discord_id", owner_id)
        .execute(),
        db.table("active_training").select("card_id").execute(),
        db.table("active_evolutions").select("card_id").eq("status", "active").execute(),
        listed_card_ids(db),
    )
    cards = cards_res.data or []
    locked = {str(row["player_card_id"]) for row in (starter_rows.data or [])}
    locked |= {str(row["card_id"]) for row in (training_rows.data or []) if row.get("card_id")}
    locked |= {str(row["card_id"]) for row in (evo_rows.data or [])}
    locked |= listed
    return [
        card for card in cards
        if str(card["id"]) not in locked
        and not card.get("is_retired")
        and not card.get("in_academy")
        and not card.get("injury_tier")
        and not card.get("in_hospital")
    ]


class OwnedView(discord.ui.View):
    def __init__(self, owner_id: int, *, timeout: float = 900) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This market session belongs to another manager.", ephemeral=True
            )
            return False
        return True


async def show_my_listings(interaction: discord.Interaction, owner_id: int) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    db = await get_client()
    rows = await db.table("transfer_listings").select(
        "id, price_coins, expires_at, player_cards(id, name, position, overall, potential, date_of_birth)"
    ).eq("seller_id", owner_id).eq("status", "active").order("created_at", desc=True).execute()
    listings = rows.data or []
    count, cap = await active_listing_count(db, owner_id)
    embed = discord.Embed(title="📋 My Transfer Listings", color=0x00FF87)
    embed.description = (
        f"**{count}/{cap}** active slots.\n"
        "You receive **90%** of each listed price; the market burns the remaining 10% tax."
    )
    if listings:
        for row in listings:
            card = row.get("player_cards") or {}
            price = int(row["price_coins"])
            embed.add_field(
                name=f"{card.get('name', 'Unknown player')} — 🪙 {price:,}",
                value=(
                    f"{card.get('position', '?')} · {card.get('overall', '?')} OVR · "
                    f"Age {effective_card_age(card)} · {card.get('potential', '?')} POT\n"
                    f"**You net: 🪙 {seller_net(price):,}**"
                ),
                inline=False,
            )
    else:
        embed.add_field(
            name="No active listings",
            value="List an eligible reserve player to start trading.",
            inline=False,
        )
    await interaction.edit_original_response(
        embed=embed, view=MyListingsView(owner_id, listings)
    )


class MyListingsView(OwnedView):
    def __init__(self, owner_id: int, listings: list[dict]) -> None:
        super().__init__(owner_id)
        self.listings = listings
        self.selected_id: str | None = None
        if listings:
            opts = [
                discord.SelectOption(
                    label=(row.get("player_cards") or {}).get("name", "Unknown")[:100],
                    description=f"🪙 {int(row['price_coins']):,} · nets {seller_net(int(row['price_coins'])):,}",
                    value=str(row["id"]),
                )
                for row in listings[:25]
            ]
            add_select_if_options(
                self,
                placeholder="Select a listing to cancel…",
                options=opts,
                row=0,
                callback=self.select_callback,
            )
            cancel = discord.ui.Button(
                label="Cancel Listing", style=discord.ButtonStyle.danger, disabled=True, row=1
            )
            cancel.callback = self.cancel_callback
            self.cancel_button = cancel
            self.add_item(cancel)
        list_button = discord.ui.Button(label="List Player", style=discord.ButtonStyle.success, row=2)
        list_button.callback = self.list_callback
        self.add_item(list_button)
        back = discord.ui.Button(label="Back to Market", style=discord.ButtonStyle.secondary, row=2)
        back.callback = self.back_callback
        self.add_item(back)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_id = interaction.data["values"][0]
        self.cancel_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            await db.rpc("cancel_transfer_listing", {
                "p_seller_id": self.owner_id, "p_listing_id": self.selected_id,
            }).execute()
            await interaction.followup.send(
                embed=success_embed("Listing cancelled. This player is available again."), ephemeral=True
            )
            await show_my_listings(interaction, self.owner_id)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    async def list_callback(self, interaction: discord.Interaction) -> None:
        await show_list_player(interaction, self.owner_id)

    async def back_callback(self, interaction: discord.Interaction) -> None:
        from apps.discord_bot.cogs.marketplace_cog import show_marketplace_hub
        await show_marketplace_hub(interaction, self.owner_id)


async def show_list_player(interaction: discord.Interaction, owner_id: int) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    db = await get_client()
    wage_msg = await wages_market_block_message(db, owner_id)
    if wage_msg:
        await interaction.followup.send(embed=error_embed(wage_msg), ephemeral=True)
        return
    cards = await _eligible_listing_cards(owner_id)
    embed = discord.Embed(title="➕ List a Player", color=0x00FF87)
    embed.description = (
        "Only healthy reserve players not in training, evolutions, or another listing can be posted.\n"
        "A fair-value guide and allowed price range are shown before you list."
    )
    if not cards:
        embed.add_field(name="No eligible players", value="Delist, bench, or finish a locked activity first.", inline=False)
    await interaction.edit_original_response(embed=embed, view=ListPlayerView(owner_id, cards))


class ListPlayerView(OwnedView):
    def __init__(self, owner_id: int, cards: list[dict]) -> None:
        super().__init__(owner_id)
        self.cards = cards
        if cards:
            opts = [
                discord.SelectOption(
                    label=card["name"][:100],
                    description=f"{card['position']} · {card['overall']} OVR · Age {effective_card_age(card)}",
                    value=str(card["id"]),
                )
                for card in cards[:25]
            ]
            add_select_if_options(
                self,
                placeholder="Choose a reserve player…",
                options=opts,
                row=0,
                callback=self.select_callback,
            )
        back = discord.ui.Button(label="Back to Listings", style=discord.ButtonStyle.secondary, row=2)
        back.callback = self.back_callback
        self.add_item(back)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        card = next((c for c in self.cards if str(c["id"]) == interaction.data["values"][0]), None)
        if not card:
            await interaction.response.send_message(embed=error_embed("Player is no longer eligible."), ephemeral=True)
            return
        await interaction.response.send_modal(ListingPriceModal(self.owner_id, card))

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_my_listings(interaction, self.owner_id)


class ListingPriceModal(discord.ui.Modal, title="Set Transfer Price"):
    price = discord.ui.TextInput(label="Price (coins)", placeholder="e.g. 2500", max_length=12)

    def __init__(self, owner_id: int, card: dict) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.card = card

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            price = int(str(self.price.value).replace(",", "").strip())
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed("Enter a whole-number coin price."), ephemeral=True
            )
            return
        fair, floor, ceil = price_bounds_for_card(
            int(self.card["overall"]), self.card["rarity"],
            age=effective_card_age(self.card), potential=self.card.get("potential"),
        )
        try:
            validate_listing_price(price, fair)
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed(
                    f"Enter a price between **{floor:,}** and **{ceil:,}** coins."
                ),
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="Confirm Transfer Listing", color=0xF1C40F)
        bargain_hint = "\n*This is below the agent fair-value guide — likely to move quickly.*" if price < fair else ""
        embed.description = (
            f"{_card_text(self.card)}\n\n"
            f"Fair agent value: **🪙 {fair:,}**\n"
            f"Allowed price: **🪙 {floor:,} – {ceil:,}**\n"
            f"Listed price: **🪙 {price:,}**\n"
            f"**You net after 10% tax: 🪙 {seller_net(price):,}**"
            f"{bargain_hint}"
        )
        await interaction.response.send_message(
            embed=embed, view=ListingConfirmView(self.owner_id, self.card, price), ephemeral=True
        )


class ListingConfirmView(OwnedView):
    def __init__(self, owner_id: int, card: dict, price: int) -> None:
        super().__init__(owner_id)
        self.card, self.price = card, price
        button = discord.ui.Button(label="Confirm Listing", style=discord.ButtonStyle.success)
        button.callback = self.confirm_callback
        self.add_item(button)

    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            lock = await assert_not_in_match(db, self.owner_id)
            if lock:
                await interaction.followup.send(embed=error_embed(lock), ephemeral=True)
                return
            wage_msg = await wages_market_block_message(db, self.owner_id)
            if wage_msg:
                await interaction.followup.send(embed=error_embed(wage_msg), ephemeral=True)
                return
            result = _data(await db.rpc("create_transfer_listing", {
                "p_seller_id": self.owner_id, "p_card_id": self.card["id"], "p_price": self.price,
            }).execute())
            await interaction.followup.send(
                embed=success_embed(
                    f"Listed **{self.card['name']}** for **🪙 {self.price:,}**. "
                    f"You will net **🪙 {int(result.get('seller_net_if_sold', seller_net(self.price))):,}**."
                ), ephemeral=True
            )
            await show_my_listings(interaction, self.owner_id)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)


class SearchMarketView(OwnedView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id)
        scouting = discord.ui.Button(label="Regen Scouting", style=discord.ButtonStyle.primary)
        scouting.callback = self.scouting_callback
        board = discord.ui.Button(label="Transfer Board", style=discord.ButtonStyle.success)
        board.callback = self.board_callback
        back = discord.ui.Button(label="Back to Market", style=discord.ButtonStyle.secondary)
        back.callback = self.back_callback
        self.add_item(scouting)
        self.add_item(board)
        self.add_item(back)

    async def scouting_callback(self, interaction: discord.Interaction) -> None:
        from apps.discord_bot.cogs.marketplace_cog import show_scouting_menu
        await show_scouting_menu(interaction, self.owner_id)

    async def board_callback(self, interaction: discord.Interaction) -> None:
        await show_transfer_board(interaction, self.owner_id)

    async def back_callback(self, interaction: discord.Interaction) -> None:
        from apps.discord_bot.cogs.marketplace_cog import show_marketplace_hub
        await show_marketplace_hub(interaction, self.owner_id)


async def show_search_market(interaction: discord.Interaction, owner_id: int) -> None:
    await interaction.response.defer(ephemeral=True)
    await interaction.edit_original_response(
        embed=discord.Embed(
            title="🔍 Search Market",
            description="Choose a **Regen Scouting** prospect or browse manager-listed cards on the **Transfer Board**.",
            color=0x00FF87,
        ),
        view=SearchMarketView(owner_id),
    )


async def _board_listings(position: str, ovr: str, age: str, pot: str) -> list[dict]:
    from datetime import datetime, timezone

    db = await get_client()
    # ponytail: PostgREST has no reliable "now()" literal — filter expiry in app; upgrade path: RPC browse.
    now_iso = datetime.now(timezone.utc).isoformat()
    result = await db.table("transfer_listings").select(
        "id, seller_id, price_coins, expires_at, player_cards(id, name, position, overall, potential, rarity, date_of_birth)"
    ).eq("status", "active").gt("expires_at", now_iso).order("created_at", desc=True).limit(50).execute()
    rows = []
    for listing in result.data or []:
        card = listing.get("player_cards") or {}
        card_age = effective_card_age(card)
        if position != "Any" and card.get("position") != position:
            continue
        if any(
            bounds and not (bounds[0] <= int(value or 0) <= bounds[1])
            for bounds, value in (
                (BANDS["ovr"][ovr], card.get("overall")),
                (BANDS["age"][age], card_age),
                (BANDS["pot"][pot], card.get("potential")),
            )
        ):
            continue
        listing["_age"] = card_age
        rows.append(listing)
        if len(rows) >= 25:
            break
    return rows


async def show_transfer_board(
    interaction: discord.Interaction,
    owner_id: int,
    *,
    position: str = "Any",
    ovr: str = "Any",
    age: str = "Any",
    pot: str = "Any",
    selected_id: str | None = None,
    stage: str = "filters",
) -> None:
    """Two-stage UI: Discord allows only one Select per action row (max 5 rows)."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    filters = [position, ovr, age, pot]
    if stage == "filters":
        embed = discord.Embed(title="🔁 Transfer Board — Filters", color=0x00FF87)
        embed.description = (
            "Pick **position** and preset bands for **OVR / age / potential**, then **Apply**.\n"
            "You pay the listed price; the seller nets 90% after tax."
        )
        embed.add_field(
            name="Current filters",
            value=f"Pos `{position}` · OVR `{ovr}` · Age `{age}` · POT `{pot}`",
            inline=False,
        )
        await interaction.edit_original_response(
            embed=embed,
            view=TransferBoardFilterView(owner_id, filters),
        )
        return

    listings = await _board_listings(position, ovr, age, pot)
    selected = next((row for row in listings if str(row["id"]) == str(selected_id)), None)
    embed = discord.Embed(title="🔁 Transfer Board", color=0x00FF87)
    embed.description = (
        f"Filters: Pos `{position}` · OVR `{ovr}` · Age `{age}` · POT `{pot}`\n"
        "Select a player to buy. You pay the listed price; seller nets 90%."
    )
    if not listings:
        embed.add_field(
            name="No matching listings",
            value=(
                "*No listings match these filters.*\n"
                "Use **Change Filters** or **Back to Market** — the listing Select is omitted when empty."
            ),
            inline=False,
        )
    elif selected:
        card, price = selected.get("player_cards") or {}, int(selected["price_coins"])
        embed.add_field(
            name=f"{card.get('name')} — 🪙 {price:,}",
            value=(
                f"{card.get('position')} · {card.get('overall')} OVR · "
                f"Age {selected['_age']} · {card.get('potential')} POT\n"
                f"Buy now for **🪙 {price:,}**."
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name=f"{len(listings)} listing(s)",
            value="Select a player to inspect and buy.",
            inline=False,
        )
    await interaction.edit_original_response(
        embed=embed,
        view=TransferBoardResultsView(owner_id, listings, filters, selected),
    )


class TransferBoardFilterView(OwnedView):
    """One Select per row — Discord forbids multiple Selects in one action row."""

    def __init__(self, owner_id: int, filters: list[str]) -> None:
        super().__init__(owner_id)
        self.filters = filters
        for index, (label, values) in enumerate((
            ("Position", POSITION_OPTIONS),
            ("OVR", tuple(BANDS["ovr"])),
            ("Age", tuple(BANDS["age"])),
            ("Potential", tuple(BANDS["pot"])),
        )):
            select = discord.ui.Select(
                placeholder=f"{label}: {self.filters[index]}",
                options=[
                    discord.SelectOption(
                        label=value, value=value, default=value == self.filters[index]
                    )
                    for value in values
                ],
                row=index,
            )
            select.callback = self._filter_callback(index)
            self.add_item(select)
        apply_btn = discord.ui.Button(label="Apply Filters", style=discord.ButtonStyle.success, row=4)
        apply_btn.callback = self.apply_callback
        self.add_item(apply_btn)
        back = discord.ui.Button(label="Back to Market", style=discord.ButtonStyle.secondary, row=4)
        back.callback = self.back_callback
        self.add_item(back)

    def _filter_callback(self, index: int):
        async def callback(interaction: discord.Interaction) -> None:
            self.filters[index] = interaction.data["values"][0]
            # Keep working state without wasting a round-trip until Apply.
            await interaction.response.edit_message(view=self)
        return callback

    async def apply_callback(self, interaction: discord.Interaction) -> None:
        await show_transfer_board(
            interaction,
            self.owner_id,
            position=self.filters[0],
            ovr=self.filters[1],
            age=self.filters[2],
            pot=self.filters[3],
            stage="results",
        )

    async def back_callback(self, interaction: discord.Interaction) -> None:
        from apps.discord_bot.cogs.marketplace_cog import show_marketplace_hub
        await show_marketplace_hub(interaction, self.owner_id)


class TransferBoardResultsView(OwnedView):
    def __init__(
        self,
        owner_id: int,
        listings: list[dict],
        filters: list[str],
        selected: dict | None,
    ) -> None:
        super().__init__(owner_id)
        self.listings, self.filters, self.selected = listings, filters, selected
        if listings:
            opts = [
                discord.SelectOption(
                    label=(row.get("player_cards") or {}).get("name", "Unknown")[:100],
                    description=(
                        f"{(row.get('player_cards') or {}).get('overall', '?')} OVR · "
                        f"🪙 {int(row['price_coins']):,}"
                    ),
                    value=str(row["id"]),
                    default=bool(selected and str(row["id"]) == str(selected["id"])),
                )
                for row in listings[:25]
            ]
            add_select_if_options(
                self,
                placeholder="Choose a listed player…",
                options=opts,
                row=0,
                callback=self.select_callback,
            )
        buy = discord.ui.Button(
            label="Buy Now",
            style=discord.ButtonStyle.success,
            disabled=not selected,
            row=1,
        )
        buy.callback = self.buy_callback
        self.add_item(buy)
        change = discord.ui.Button(label="Change Filters", style=discord.ButtonStyle.primary, row=1)
        change.callback = self.filters_callback
        self.add_item(change)
        back = discord.ui.Button(label="Back to Market", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self.back_callback
        self.add_item(back)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        await show_transfer_board(
            interaction,
            self.owner_id,
            position=self.filters[0],
            ovr=self.filters[1],
            age=self.filters[2],
            pot=self.filters[3],
            selected_id=interaction.data["values"][0],
            stage="results",
        )

    async def buy_callback(self, interaction: discord.Interaction) -> None:
        if not self.selected:
            await interaction.response.send_message(
                embed=error_embed("Select a listing first."), ephemeral=True
            )
            return
        card = self.selected.get("player_cards") or {}
        price = int(self.selected["price_coins"])
        embed = discord.Embed(
            title="Confirm Purchase",
            color=0xF1C40F,
            description=(
                f"{_card_text(card)}\n\n**Price: 🪙 {price:,}**\n"
                "You pay the listed price. Seller nets 90% after market tax."
            ),
        )
        await interaction.response.send_message(
            embed=embed,
            view=BuyConfirmView(self.owner_id, self.selected, self.filters),
            ephemeral=True,
        )

    async def filters_callback(self, interaction: discord.Interaction) -> None:
        await show_transfer_board(
            interaction,
            self.owner_id,
            position=self.filters[0],
            ovr=self.filters[1],
            age=self.filters[2],
            pot=self.filters[3],
            stage="filters",
        )

    async def back_callback(self, interaction: discord.Interaction) -> None:
        from apps.discord_bot.cogs.marketplace_cog import show_marketplace_hub
        await show_marketplace_hub(interaction, self.owner_id)


class BuyConfirmView(OwnedView):
    def __init__(self, owner_id: int, listing: dict, filters: list[str]) -> None:
        super().__init__(owner_id)
        self.listing, self.filters = listing, filters
        confirm = discord.ui.Button(label="Confirm Buy Now", style=discord.ButtonStyle.success)
        confirm.callback = self.confirm_callback
        self.add_item(confirm)

    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            result = _data(await db.rpc("purchase_transfer_listing", {
                "p_buyer_id": self.owner_id,
                "p_listing_id": self.listing["id"],
                "p_expected_price": int(self.listing["price_coins"]),
            }).execute())
            await interaction.followup.send(
                embed=success_embed(
                    f"Bought **{result.get('player_name', 'player')}** for **🪙 {int(result.get('gross_price', self.listing['price_coins'])):,}**."
                ), ephemeral=True
            )
            await show_transfer_board(interaction, self.owner_id, position=self.filters[0], ovr=self.filters[1], age=self.filters[2], pot=self.filters[3], stage="results")
        except Exception as exc:
            message = str(exc).lower()
            if "insufficient" in message:
                friendly = "You do not have enough coins for this player."
            elif "own listing" in message:
                friendly = "You cannot buy your own listing."
            elif "roster full" in message:
                friendly = "Your senior roster is full. Free a slot before buying."
            elif "price mismatch" in message:
                friendly = "This listing price changed. Refresh the board and review it again."
            elif "sold" in message or "not found" in message or "expired" in message:
                friendly = "This listing is no longer available — another manager may have bought it."
            else:
                friendly = str(exc)
            await interaction.followup.send(embed=error_embed(friendly), ephemeral=True)
