# apps/discord_bot/cogs/squad_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.embeds.squad_embeds import get_slot_position, roster_embed
from apps.discord_bot.core.pitch_generator import generate_squad_pitch, generate_roster_grid
from apps.discord_bot.core.view_helpers import disable_view_on_timeout
from apps.discord_bot.core.select_helpers import rebuild_select_options
from match_engine import reserve_fits_formation_slot
from apps.discord_bot.middleware.match_lock import assert_not_in_match

logger = logging.getLogger(__name__)


def _swap_selection_ready(starter_id: str | None, reserve_id: str | None) -> bool:
    return bool(
        starter_id and reserve_id
        and starter_id != "none"
        and reserve_id != "none"
    )

async def fetch_squad_data(user_id: int):
    db = await get_client()
    
    # 1. Fetch club/manager details from players
    player_res = await db.table("players").select("club_name, manager_name, squad_invalid").eq("discord_id", user_id).maybe_single().execute()
    player_data = player_res.data if player_res else None
    club_name = player_data.get("club_name", "Unknown Club") if player_data else "Unknown Club"
    squad_invalid = bool(player_data.get("squad_invalid")) if player_data else False
    
    # 2. Fetch squad formation
    squad_res = await db.table("squads").select("formation").eq("discord_id", user_id).maybe_single().execute()
    formation = squad_res.data.get("formation", "4-4-2") if (squad_res and squad_res.data) else "4-4-2"
    
    # 3. Fetch current squad assignments
    assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", user_id).execute()
    assignments = {a["position_slot"]: a["player_cards"] for a in assignments_res.data if a.get("player_cards")}
    
    # 4. Fetch total owned player cards count
    cards_res = await db.table("player_cards").select("id").eq("owner_id", user_id).execute()
    total_cards = len(cards_res.data) if cards_res.data else 0
    reserves_count = max(0, total_cards - len(assignments))
    
    # 5. Check match lock
    lock_res = await db.table("match_locks").select("*").eq("discord_id", user_id).maybe_single().execute()
    is_locked = bool(lock_res.data) if lock_res else False
    
    return club_name, formation, assignments, reserves_count, is_locked, squad_invalid

def get_players_list_for_pitch(formation: str, assignments: dict[int, dict]) -> list[dict]:
    players_list = []
    for slot in range(1, 12):
        card = assignments.get(slot)
        if card:
            players_list.append({
                "name": card["name"],
                "overall": card["overall"],
                "position": card["position"],
                "rarity": card.get("rarity", "Common")
            })
        else:
            req_pos = get_slot_position(formation, slot)
            players_list.append({
                "name": "Empty Slot",
                "overall": 0,
                "position": req_pos,
                "rarity": "Common"
            })
    return players_list

def build_hub_embed(
    club_name: str,
    formation: str,
    assignments: dict[int, dict],
    reserves_count: int,
    is_locked: bool,
    squad_invalid: bool = False,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📋 {club_name} Squad Management",
        color=0x00FF87
    )
    
    embed.add_field(name="Tactical Formation", value=f"`{formation}`", inline=True)
    embed.add_field(name="Reserves", value=f"👥 {reserves_count} Reserves Available", inline=True)
    
    notes: list[str] = []
    if is_locked:
        notes.append("🔒 **Squad is locked. A match is currently in progress.**")
    if squad_invalid:
        notes.append(
            "⚠️ **Starting XI invalid after a retirement.** Fill empty slots, then save — matches are blocked until then."
        )
    if notes:
        embed.description = "\n".join(notes)
        
    embed.set_image(url="attachment://squad_pitch.png")
    return embed


class SquadHubView(discord.ui.View):
    def __init__(self, user_id: int, club_name: str, formation: str, assignments: dict[int, dict], reserves_count: int, is_locked: bool) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.club_name = club_name
        self.formation = formation
        self.assignments = assignments
        self.reserves_count = reserves_count
        self.is_locked = is_locked
        self.message: discord.Message | None = None
        self.setup_buttons()

    def setup_buttons(self) -> None:
        self.clear_items()

        change_formation_btn = discord.ui.Button(label="Change Formation", style=discord.ButtonStyle.primary, custom_id="squad_change_formation", emoji="🔄", disabled=self.is_locked)
        swap_players_btn = discord.ui.Button(label="Swap Players", style=discord.ButtonStyle.primary, custom_id="squad_swap_players", emoji="🔁", disabled=self.is_locked)
        full_roster_btn = discord.ui.Button(label="Full Roster", style=discord.ButtonStyle.secondary, custom_id="squad_full_roster", emoji="👥", disabled=self.is_locked)
        tactics_btn = discord.ui.Button(label="Tactics (Soon)", style=discord.ButtonStyle.secondary, custom_id="squad_tactics", emoji="⚙️", disabled=True)

        change_formation_btn.callback = self.on_change_formation
        swap_players_btn.callback = self.on_swap_players
        full_roster_btn.callback = self.on_full_roster

        self.add_item(change_formation_btn)
        self.add_item(swap_players_btn)
        self.add_item(full_roster_btn)
        self.add_item(tactics_btn)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True

    async def on_change_formation(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        formation_view = SquadFormationView(self.user_id, self)
        await interaction.edit_original_response(embed=formation_view.get_embed(), view=formation_view, attachments=[])

    async def on_swap_players(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        
        try:
            db = await get_client()
            
            # Fetch all cards sorted by overall descending
            cards_res = await db.table("player_cards").select("*").eq("owner_id", self.user_id).order("overall", desc=True).execute()
            all_cards = cards_res.data or []
            
            # Get assigned IDs
            assigned_ids = {c["id"] for c in self.assignments.values()}
            
            # Filter reserves (not assigned) and cap at 25 highest OVR
            reserves = [c for c in all_cards if c["id"] not in assigned_ids][:25]
            starters = [self.assignments[slot] for slot in range(1, 12) if slot in self.assignments]
            
            swap_view = SquadSwapView(self.user_id, self, starters, reserves)
            await interaction.edit_original_response(embed=swap_view.get_embed(), view=swap_view, attachments=[])
        except Exception as e:
            logger.exception("Failed to prepare swap view.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    async def on_full_roster(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        
        try:
            db = await get_client()
            cards_res = await db.table("player_cards").select("*").eq("owner_id", self.user_id).order("overall", desc=True).execute()
            all_cards = cards_res.data or []
            
            roster_view = SquadRosterView(self.user_id, self, all_cards)
            page_cards = all_cards[:8]
            roster_file = await generate_roster_grid(page_cards)
            
            await interaction.edit_original_response(embed=roster_view.get_embed(), view=roster_view, attachments=[roster_file])
        except Exception as e:
            logger.exception("Failed to prepare roster view.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)


class SquadFormationView(discord.ui.View):
    def __init__(self, user_id: int, hub_view: SquadHubView) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.hub_view = hub_view
        
        options = [
            discord.SelectOption(label="4-4-2", description="Standard balanced formation", emoji="⚽"),
            discord.SelectOption(label="4-3-3", description="Attacking formation with wingers", emoji="⚔️"),
            discord.SelectOption(label="3-5-2", description="Midfield dominance formation", emoji="🛡️"),
            discord.SelectOption(label="4-2-3-1", description="Modern tactical formation", emoji="🧠"),
            discord.SelectOption(label="5-3-2", description="Defensive counter-attacking formation", emoji="🚌"),
        ]
        self.select = discord.ui.Select(placeholder="Select a formation...", min_values=1, max_values=1, options=options)
        self.select.callback = self.on_select_formation
        self.add_item(self.select)

        back_btn = discord.ui.Button(label="Back to Hub", style=discord.ButtonStyle.secondary, emoji="🔙")
        back_btn.callback = self.on_back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)

    def get_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🔄 Change Squad Formation",
            description="Select your new starting formation. Changing formations will automatically assign players to match the positions required.",
            color=0x00FF87
        )

    async def on_back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        club_name, formation, assignments, reserves_count, is_locked, squad_invalid = await fetch_squad_data(self.user_id)
        players_list = get_players_list_for_pitch(formation, assignments)
        pitch_file = await generate_squad_pitch(formation, players_list)
        
        self.hub_view.club_name = club_name
        self.hub_view.formation = formation
        self.hub_view.assignments = assignments
        self.hub_view.reserves_count = reserves_count
        self.hub_view.is_locked = is_locked
        self.hub_view.setup_buttons()
        await interaction.edit_original_response(embed=build_hub_embed(club_name, formation, assignments, reserves_count, is_locked, squad_invalid), attachments=[pitch_file], view=self.hub_view)

    async def on_select_formation(self, interaction: discord.Interaction) -> None:
        chosen_formation = self.select.values[0]
        await interaction.response.defer()
        
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.user_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return
            
            # Fetch all owned players
            res = await db.table("player_cards").select("*").eq("owner_id", self.user_id).execute()
            all_cards = res.data or []
            
            assigned_cards = {}  # slot -> card
            used_ids = set()
            
            # Positions needed for this formation
            positions_needed = []
            for slot in range(1, 12):
                positions_needed.append((slot, get_slot_position(chosen_formation, slot)))
                
            # First pass: assign natural positions (slot 1 always GK)
            for slot, pos in positions_needed:
                if slot == 1:
                    matching_players = [c for c in all_cards if c["position"] == "GK" and c["id"] not in used_ids]
                else:
                    matching_players = [c for c in all_cards if c["position"] == pos and c["id"] not in used_ids]
                if matching_players:
                    matching_players.sort(key=lambda x: x["overall"], reverse=True)
                    best_player = matching_players[0]
                    assigned_cards[slot] = best_player
                    used_ids.add(best_player["id"])
            
            # Second pass: fill empty slots with highest overall unused players (out-of-position fallback)
            for slot, pos in positions_needed:
                if slot not in assigned_cards:
                    if slot == 1:
                        gk_pool = [c for c in all_cards if c["position"] == "GK" and c["id"] not in used_ids]
                        if gk_pool:
                            gk_pool.sort(key=lambda x: x["overall"], reverse=True)
                            assigned_cards[slot] = gk_pool[0]
                            used_ids.add(gk_pool[0]["id"])
                        continue
                    unused_players = [c for c in all_cards if c["id"] not in used_ids]
                    if unused_players:
                        unused_players.sort(key=lambda x: x["overall"], reverse=True)
                        best_fallback = unused_players[0]
                        assigned_cards[slot] = best_fallback
                        used_ids.add(best_fallback["id"])
            
            payload = [{"slot": slot, "card_id": str(card["id"])} for slot, card in assigned_cards.items()]
            await db.rpc("set_formation_and_assignments", {
                "p_discord_id": self.user_id,
                "p_formation": chosen_formation,
                "p_assignments": payload,
            }).execute()
                
            # Return to main Hub with success message
            club_name, formation, assignments, reserves_count, is_locked, squad_invalid = await fetch_squad_data(self.user_id)
            players_list = get_players_list_for_pitch(formation, assignments)
            pitch_file = await generate_squad_pitch(formation, players_list)
            
            self.hub_view.club_name = club_name
            self.hub_view.formation = formation
            self.hub_view.assignments = assignments
            self.hub_view.reserves_count = reserves_count
            self.hub_view.is_locked = is_locked
            self.hub_view.setup_buttons()
            
            success_msg = f"Successfully set formation to **{chosen_formation}** and auto-assigned starters!"
            embed = build_hub_embed(club_name, formation, assignments, reserves_count, is_locked, squad_invalid)
            embed.description = f"✅ {success_msg}"
            
            await interaction.edit_original_response(embed=embed, attachments=[pitch_file], view=self.hub_view)
            
        except Exception as e:
            logger.exception("Failed to change formation and auto-assign.")
            err_embed = self.get_embed()
            err_embed.description = f"❌ **Error changing formation:** {str(e)}\n\nSelect another formation or click Back."
            await interaction.edit_original_response(embed=err_embed, view=self)


class SquadSwapView(discord.ui.View):
    def __init__(self, user_id: int, hub_view: SquadHubView, starters: list[dict], reserves: list[dict]) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.hub_view = hub_view
        self.starters = starters
        self.reserves = reserves
        
        self.selected_starter_id: str | None = None
        self.selected_reserve_id: str | None = None
        
        self.setup_components()

    def _eligible_reserves(self) -> list[dict]:
        """Reserves that can fill the selected starter's formation slot (and aren't injured)."""
        healthy = [c for c in self.reserves if not c.get("injury_tier")]
        if not self.selected_starter_id:
            return healthy
        card_to_slot = {card["id"]: slot for slot, card in self.hub_view.assignments.items()}
        slot = card_to_slot.get(self.selected_starter_id)
        if slot is None:
            return healthy
        formation = self.hub_view.formation
        return [
            c
            for c in healthy
            if reserve_fits_formation_slot(formation, slot, str(c.get("position") or ""))
        ]

    def setup_components(self) -> None:
        self.clear_items()
        card_to_slot = {card["id"]: slot for slot, card in self.hub_view.assignments.items()}
        eligible = self._eligible_reserves()
        if self.selected_reserve_id and not any(
            c["id"] == self.selected_reserve_id for c in eligible
        ):
            self.selected_reserve_id = None

        bench_opts = rebuild_select_options(
            self.starters,
            self.selected_starter_id,
            label_fn=lambda c: f"Slot {card_to_slot.get(c['id'], '?')}: {c['name']}",
            description_fn=lambda c: f"{c['position']} | {c['overall']} OVR",
        )
        if not bench_opts:
            bench_opts = [discord.SelectOption(label="No starters available", value="none")]
        bench_select = discord.ui.Select(
            placeholder="Select Player to Bench...",
            options=bench_opts,
            min_values=1,
            max_values=1,
            custom_id="bench_select",
            disabled=not self.starters,
        )
        bench_select.callback = self.on_bench_select
        self.add_item(bench_select)

        if eligible:
            reserve_opts = rebuild_select_options(
                eligible,
                self.selected_reserve_id,
                label_fn=lambda c: c["name"],
                description_fn=lambda c: f"{c['position']} | {c['overall']} OVR",
            )
        elif self.selected_starter_id:
            reserve_opts = [
                discord.SelectOption(
                    label="No compatible reserves for this slot",
                    value="none",
                )
            ]
        else:
            reserve_opts = [discord.SelectOption(label="No reserves available", value="none")]
        start_select = discord.ui.Select(
            placeholder=(
                "Select compatible reserve..."
                if self.selected_starter_id
                else "Select Player to Start..."
            ),
            options=reserve_opts,
            min_values=1,
            max_values=1,
            custom_id="start_select",
            disabled=(len(eligible) == 0),
        )
        start_select.callback = self.on_start_select
        self.add_item(start_select)
        
        # Confirm Swap Button
        can_confirm = _swap_selection_ready(self.selected_starter_id, self.selected_reserve_id)
        self.confirm_btn = discord.ui.Button(
            label="Confirm Swap",
            style=discord.ButtonStyle.success,
            emoji="✅",
            disabled=not can_confirm,
        )
        self.confirm_btn.callback = self.on_confirm
        self.add_item(self.confirm_btn)
        
        # Back Button
        back_btn = discord.ui.Button(
            label="Back to Hub",
            style=discord.ButtonStyle.secondary,
            emoji="🔙"
        )
        back_btn.callback = self.on_back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔁 Swap Players",
            description=(
                "Select a starter to bench, then a **compatible** reserve for that slot "
                "(e.g. only **GK** can replace the goalkeeper)."
            ),
            color=0x00FF87
        )
        if self.selected_starter_id:
            starter_card = next((c for c in self.starters if c["id"] == self.selected_starter_id), None)
            starter_name = starter_card["name"] if starter_card else "Unknown"
            card_to_slot = {card["id"]: slot for slot, card in self.hub_view.assignments.items()}
            slot = card_to_slot.get(self.selected_starter_id)
            req = get_slot_position(self.hub_view.formation, slot) if slot else "?"
            embed.add_field(
                name="Out",
                value=f"⬇️ {starter_name} (needs **{req}**)",
                inline=True,
            )
        if self.selected_reserve_id:
            reserve_card = next((c for c in self.reserves if c["id"] == self.selected_reserve_id), None)
            reserve_name = reserve_card["name"] if reserve_card else "Unknown"
            embed.add_field(name="In", value=f"⬆️ {reserve_name}", inline=True)
        return embed

    async def on_bench_select(self, interaction: discord.Interaction) -> None:
        self.selected_starter_id = interaction.data["values"][0]
        if self.selected_starter_id == "none":
            self.selected_starter_id = None
        # Slot change may invalidate the previously picked reserve.
        self.selected_reserve_id = None
        self.setup_components()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def on_start_select(self, interaction: discord.Interaction) -> None:
        self.selected_reserve_id = interaction.data["values"][0]
        if self.selected_reserve_id == "none":
            self.selected_reserve_id = None
        self.setup_components()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def on_back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        club_name, formation, assignments, reserves_count, is_locked, squad_invalid = await fetch_squad_data(self.user_id)
        players_list = get_players_list_for_pitch(formation, assignments)
        pitch_file = await generate_squad_pitch(formation, players_list)
        
        self.hub_view.club_name = club_name
        self.hub_view.formation = formation
        self.hub_view.assignments = assignments
        self.hub_view.reserves_count = reserves_count
        self.hub_view.is_locked = is_locked
        self.hub_view.setup_buttons()
        await interaction.edit_original_response(embed=build_hub_embed(club_name, formation, assignments, reserves_count, is_locked, squad_invalid), attachments=[pitch_file], view=self.hub_view)

    async def on_confirm(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.user_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            card_to_slot = {card["id"]: slot for slot, card in self.hub_view.assignments.items()}
            slot = card_to_slot.get(self.selected_starter_id)
            if not slot:
                raise ValueError("Could not find the squad slot of the selected starter.")

            reserve_res = await db.table("player_cards").select(
                "id, position, injury_tier, name"
            ).eq("id", self.selected_reserve_id).eq("owner_id", self.user_id).maybe_single().execute()
            if not reserve_res or not reserve_res.data:
                raise ValueError("Reserve player no longer available.")

            if reserve_res.data.get("injury_tier"):
                raise ValueError(
                    f"**{reserve_res.data.get('name', 'Player')}** is injured and cannot enter the starting XI."
                )

            reserve_pos = reserve_res.data["position"]
            if not reserve_fits_formation_slot(self.hub_view.formation, slot, reserve_pos):
                required = get_slot_position(self.hub_view.formation, slot)
                raise ValueError(
                    f"**{reserve_pos}** cannot play **{required}** in this formation. Pick a compatible reserve."
                )

            await db.rpc("swap_squad_players", {
                "p_discord_id": self.user_id,
                "p_slot": slot,
                "p_reserve_card_id": self.selected_reserve_id,
            }).execute()
            
            # Refresh hub and transition
            club_name, formation, assignments, reserves_count, is_locked, squad_invalid = await fetch_squad_data(self.user_id)
            players_list = get_players_list_for_pitch(formation, assignments)
            pitch_file = await generate_squad_pitch(formation, players_list)
            
            self.hub_view.club_name = club_name
            self.hub_view.formation = formation
            self.hub_view.assignments = assignments
            self.hub_view.reserves_count = reserves_count
            self.hub_view.is_locked = is_locked
            self.hub_view.setup_buttons()
            
            starter_card = next((c for c in self.starters if c["id"] == self.selected_starter_id), None)
            reserve_card = next((c for c in self.reserves if c["id"] == self.selected_reserve_id), None)
            s_name = starter_card["name"] if starter_card else "Unknown"
            r_name = reserve_card["name"] if reserve_card else "Unknown"
            
            success_msg = f"Successfully swapped **{s_name}** out for **{r_name}** in Slot {slot}!"
            embed = build_hub_embed(club_name, formation, assignments, reserves_count, is_locked, squad_invalid)
            embed.description = f"✅ {success_msg}"
            
            await interaction.edit_original_response(embed=embed, attachments=[pitch_file], view=self.hub_view)
            
        except ValueError as e:
            # Expected validation (position mismatch, injured, missing card) — not a crash.
            err_embed = self.get_embed()
            err_embed.description = f"❌ {e}\n\nPick a compatible reserve or click Back."
            await interaction.edit_original_response(embed=err_embed, view=self)
        except Exception:
            logger.exception("Failed to swap players.")
            err_embed = self.get_embed()
            err_embed.description = (
                "❌ **Error swapping players.** Try again or click Back."
            )
            await interaction.edit_original_response(embed=err_embed, view=self)


class SquadRosterView(discord.ui.View):
    def __init__(self, user_id: int, hub_view: SquadHubView, cards: list[dict], per_page: int = 8) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.hub_view = hub_view
        self.cards = cards
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(cards) + per_page - 1) // per_page)
        
        self.setup_buttons()

    def setup_buttons(self) -> None:
        self.clear_items()
        
        prev_btn = discord.ui.Button(
            label="◀ Previous",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0)
        )
        prev_btn.callback = self.on_prev
        self.add_item(prev_btn)
        
        next_btn = discord.ui.Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.total_pages - 1)
        )
        next_btn.callback = self.on_next
        self.add_item(next_btn)
        
        back_btn = discord.ui.Button(
            label="Back to Hub",
            style=discord.ButtonStyle.primary,
            emoji="🔙"
        )
        back_btn.callback = self.on_back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True

    def get_embed(self) -> discord.Embed:
        return roster_embed(self.cards, self.current_page, self.total_pages)

    async def on_prev(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.current_page -= 1
        self.setup_buttons()
        
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_cards = self.cards[start:end]
        roster_file = await generate_roster_grid(page_cards)
        
        await interaction.edit_original_response(embed=self.get_embed(), view=self, attachments=[roster_file])

    async def on_next(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.current_page += 1
        self.setup_buttons()
        
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_cards = self.cards[start:end]
        roster_file = await generate_roster_grid(page_cards)
        
        await interaction.edit_original_response(embed=self.get_embed(), view=self, attachments=[roster_file])

    async def on_back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        club_name, formation, assignments, reserves_count, is_locked, squad_invalid = await fetch_squad_data(self.user_id)
        players_list = get_players_list_for_pitch(formation, assignments)
        pitch_file = await generate_squad_pitch(formation, players_list)
        
        self.hub_view.club_name = club_name
        self.hub_view.formation = formation
        self.hub_view.assignments = assignments
        self.hub_view.reserves_count = reserves_count
        self.hub_view.is_locked = is_locked
        self.hub_view.setup_buttons()
        await interaction.edit_original_response(embed=build_hub_embed(club_name, formation, assignments, reserves_count, is_locked, squad_invalid), attachments=[pitch_file], view=self.hub_view)


async def show_squad_hub(interaction: discord.Interaction, owner_id: int) -> None:
    """Shared entry for `/squad` and `/profile` → View Club Stats. Caller must defer first."""
    club_name, formation, assignments, reserves_count, is_locked, squad_invalid = await fetch_squad_data(owner_id)
    players_list = get_players_list_for_pitch(formation, assignments)
    pitch_file = await generate_squad_pitch(formation, players_list)
    view = SquadHubView(owner_id, club_name, formation, assignments, reserves_count, is_locked)
    embed = build_hub_embed(club_name, formation, assignments, reserves_count, is_locked, squad_invalid)

    if interaction.message is not None:
        try:
            await interaction.followup.edit_message(
                interaction.message.id,
                embed=embed,
                view=view,
                attachments=[pitch_file],
            )
            view.message = interaction.message
            return
        except discord.NotFound:
            pass

    try:
        await interaction.edit_original_response(
            embed=embed, view=view, attachments=[pitch_file]
        )
        view.message = await interaction.original_response()
    except discord.HTTPException:
        msg = await interaction.followup.send(
            embed=embed, file=pitch_file, view=view, ephemeral=True
        )
        view.message = msg


class SquadCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="squad", description="Access the Unified Squad Management Hub.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def squad(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            await show_squad_hub(interaction, interaction.user.id)
        except Exception as e:
            logger.exception("Failed to load squad hub.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while loading Squad Hub: {str(e)}"),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SquadCog(bot))
