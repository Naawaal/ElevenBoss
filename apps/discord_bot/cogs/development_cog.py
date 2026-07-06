# apps/discord_bot/cogs/development_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands
from postgrest.exceptions import APIError
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.core.select_helpers import rebuild_select_options
from apps.discord_bot.core.view_helpers import disable_view_on_timeout
from apps.discord_bot.middleware.match_lock import assert_not_in_match

logger = logging.getLogger(__name__)

STAT_DRILLS = {
    "pac_sprint": "⚡ Pace Sprint",
    "sho_finishing": "🎯 Finishing Drill",
    "pas_distribution": "🧠 Distribution Drill",
    "dri_dribble": "👟 Dribbling Drill",
    "def_tackling": "🛡️ Tackling Drill",
    "phy_strength": "💪 Strength Drill",
}

EVOLUTION_TRACKS = {
    "pace_boost": {
        "name": "⚡ Pace Masterclass",
        "description": "Improve player speed and burst.",
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
        "description": "Construct rock-solid defense foundation.",
        "metric": "matches",
        "goal": 3,
        "reward_stat": "def",
        "reward_val": 5
    }
}

def _api_message(exc: Exception) -> str:
    if isinstance(exc, APIError) and exc.args and isinstance(exc.args[0], dict):
        return exc.args[0].get("message", str(exc))
    return str(exc)


async def _edit_hub_message(interaction: discord.Interaction, embed: discord.Embed, view: discord.ui.View) -> None:
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


# --- Navigation / Switch helpers ---
async def show_hub(interaction: discord.Interaction, owner_id: int):
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data if player_res else None
    
    embed = discord.Embed(
        title="🏋️‍♂️ Development Center",
        description=f"Welcome to **{player['club_name']}** development center. Train stats, fuse duplicate cards, evolve playstyles, or allocate skill points.",
        color=0x00FF87
    )
    view = DevelopmentHubView(owner_id)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)

# --- VIEWS ---

class DevelopmentHubView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🏋️ Training Drills", custom_id="hub_drills", row=0)
    async def training_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await show_training_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🧬 Evolutions", custom_id="hub_evos", row=0)
    async def evolutions_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await show_evols_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⭐ Allocate Skills", custom_id="hub_skills", row=1)
    async def skills_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await show_skills_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.danger, label="🔥 Card Fusion", custom_id="hub_fusion", row=1)
    async def fusion_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await show_card_fusion_menu(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


# --- 1. STAT DRILL TRAINING ---

async def show_training_menu(interaction: discord.Interaction, owner_id: int) -> None:
    db = await get_client()
    energy_res = await db.rpc("sync_training_energy", {"p_club_id": owner_id}).execute()
    energy = energy_res.data or {}

    roster_res = await db.table("player_cards").select("*").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    evo_res = await db.table("active_evolutions").select("card_id").execute()
    evo_ids = {e["card_id"] for e in (evo_res.data or [])}
    eligible_players = [p for p in roster if p["id"] not in evo_ids]

    training_energy = energy.get("training_energy", 0)
    daily_count = energy.get("daily_drill_count", 0)
    daily_limit = energy.get("daily_drill_limit", 20)

    embed = discord.Embed(
        title="🏋️ Stat Training Drills",
        description=(
            "Spend **Training Energy** and coins to boost a player's core stats.\n\n"
            f"⚡ **Training Energy**: `{training_energy}/100` *(+25/hour)*\n"
            f"📅 **Daily Drills**: `{daily_count}/{daily_limit}`\n"
            f"💪 **Cost per drill**: `15 energy` + `5 × player OVR` coins"
        ),
        color=0x00FF87,
    )
    if not eligible_players:
        embed.add_field(
            name="No Eligible Players",
            value="All roster cards are locked in an active evolution track.",
            inline=False,
        )

    await _edit_hub_message(interaction, embed, StatDrillView(owner_id, eligible_players[:25]))


class StatDrillView(discord.ui.View):
    def __init__(self, owner_id: int, eligible_players: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.selected_card_id: str | None = None
        self.selected_drill: str | None = None
        self.eligible_players = eligible_players
        self._build_items()

    def _build_items(self) -> None:
        self.clear_items()
        if self.eligible_players:
            player_options = rebuild_select_options(
                self.eligible_players,
                self.selected_card_id,
                label_fn=lambda p: p["name"],
                description_fn=lambda p: f"{p['overall']} OVR | Lvl {p['level']} | {p['position']}",
            )
            self.player_select = discord.ui.Select(
                placeholder="Select a player to train...",
                min_values=1,
                max_values=1,
                options=player_options,
                row=0,
            )
            self.player_select.callback = self.player_select_callback
            self.add_item(self.player_select)

            drill_options = [
                discord.SelectOption(
                    label=name,
                    value=drill_id,
                    default=(self.selected_drill == drill_id),
                )
                for drill_id, name in STAT_DRILLS.items()
            ]
            self.drill_select = discord.ui.Select(
                placeholder="Select stat drill...",
                min_values=1,
                max_values=1,
                options=drill_options,
                row=1,
            )
            self.drill_select.callback = self.drill_select_callback
            self.add_item(self.drill_select)

            self.run_btn = discord.ui.Button(
                style=discord.ButtonStyle.success, label="Run Drill", disabled=True, row=2
            )
            self.run_btn.callback = self.run_drill_callback
            self.add_item(self.run_btn)

        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", row=2)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_hub(interaction, self.owner_id)

    def _update_run_btn(self) -> None:
        if hasattr(self, "run_btn"):
            self.run_btn.disabled = not (self.selected_card_id and self.selected_drill)

    async def player_select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_card_id = self.player_select.values[0]
        self._update_run_btn()
        self._build_items()
        await _edit_hub_message(interaction, interaction.message.embeds[0], self)

    async def drill_select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_drill = self.drill_select.values[0]
        self._update_run_btn()
        self._build_items()
        await _edit_hub_message(interaction, interaction.message.embeds[0], self)

    async def run_drill_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            res = await db.rpc("process_stat_drill", {
                "p_owner_id": self.owner_id,
                "p_card_id": self.selected_card_id,
                "p_drill_id": self.selected_drill,
            }).execute()
            result = res.data or {}
            selected_p = next(p for p in self.eligible_players if str(p["id"]) == str(self.selected_card_id))
            stat = str(result.get("stat", "")).upper()
            levels = int(result.get("levels_gained", 0))
            new_ovr = result.get("new_ovr", selected_p["overall"])
            coins_spent = result.get("coins_spent", 0)

            msg = (
                f"**{selected_p['name']}** completed **{STAT_DRILLS.get(self.selected_drill, self.selected_drill)}**.\n"
                f"• Stat trained: `+{levels} {stat}`\n"
                f"• New OVR: **{new_ovr}**\n"
                f"• Spent: `15 energy` + `🪙 {coins_spent:,} coins`"
            )
            if levels == 0:
                msg += "\n\n*Stat XP banked — keep drilling to level up this stat.*"

            await interaction.followup.send(embed=success_embed(msg), ephemeral=True)
            await show_training_menu(interaction, self.owner_id)

        except Exception as exc:
            logger.exception("Failed running stat drill.")
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


# --- 2. CARD FUSION (sacrifice one card to level up another) ---

async def _fetch_card_locks(owner_id: int) -> tuple[set[str], set[str]]:
    """Returns (starting_11_ids, active_evolution_ids)."""
    db = await get_client()
    assignments_res = await db.table("squad_assignments").select("player_card_id").eq("discord_id", owner_id).execute()
    starting_ids = {str(a["player_card_id"]) for a in (assignments_res.data or [])}
    evo_res = await db.table("active_evolutions").select("card_id").execute()
    evo_ids = {str(e["card_id"]) for e in (evo_res.data or [])}
    return starting_ids, evo_ids


async def show_card_fusion_menu(interaction: discord.Interaction, owner_id: int) -> None:
    db = await get_client()
    cards_res = await db.table("player_cards").select("*").eq("owner_id", owner_id).order("overall", desc=True).execute()
    cards = cards_res.data or []

    if len(cards) < 2:
        embed = error_embed("You need at least 2 player cards to fuse (one to upgrade and one to sacrifice).")
        await _edit_hub_message(interaction, embed, CardFusionView(owner_id, [], []))
        return

    starting_ids, evo_ids = await _fetch_card_locks(owner_id)
    target_pool = [c for c in cards if str(c["id"]) not in evo_ids][:25]
    sacrifice_pool = [
        c for c in cards
        if str(c["id"]) not in starting_ids and str(c["id"]) not in evo_ids
    ][:25]

    if not target_pool or not sacrifice_pool:
        msg = "No eligible cards for fusion."
        if not target_pool:
            msg = "No eligible upgrade targets. Players in an active evolution cannot be upgraded."
        elif not sacrifice_pool:
            msg = "No eligible sacrifice cards. Starting XI and evolution-locked players cannot be fused."
        embed = error_embed(msg)
        await _edit_hub_message(interaction, embed, CardFusionView(owner_id, target_pool, sacrifice_pool))
        return

    embed = discord.Embed(
        title="🔥 Card Fusion",
        description=(
            "Sacrifice a **bench card** to feed XP into a **keeper**. The sacrificed card is **permanently deleted**.\n\n"
            "*Sacrifice: not in starting XI or active evolution. "
            "Keeper: not in active evolution.*"
        ),
        color=0xFF6B35,
    )
    embed.set_footer(text="Showing your top 25 eligible cards per role.")
    await _edit_hub_message(interaction, embed, CardFusionView(owner_id, target_pool, sacrifice_pool))


class FusionKeeperSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Select keeper to upgrade...",
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.keeper_id = self.values[0]
        self.view._rebuild_options()
        await interaction.response.edit_message(view=self.view)


class FusionSacrificeSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Select card to sacrifice...",
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.sacrifice_id = self.values[0]
        self.view._rebuild_options()
        await interaction.response.edit_message(view=self.view)


class FusionConfirmButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Confirm Fusion",
            disabled=True,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self.view.keeper_id or not self.view.sacrifice_id:
            return

        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self.view)

        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, interaction.user.id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            await db.rpc("train_with_fodder", {
                "p_owner_id": interaction.user.id,
                "p_target_id": self.view.keeper_id,
                "p_fodder_id": self.view.sacrifice_id,
            }).execute()

            target_res = await db.table("player_cards").select("*").eq("id", self.view.keeper_id).maybe_single().execute()
            keeper = target_res.data
            if not keeper:
                raise ValueError("Could not find the keeper card after fusion.")

            new_level = keeper["level"]
            progress = f"📈 **Level**: {new_level}\n⭐ **OVR**: {keeper['overall']}"

            embed = discord.Embed(
                title="🔥 Fusion Complete!",
                description=f"**{keeper['name']}** absorbed the sacrificed card.",
                color=0x00FF87,
            )
            embed.add_field(name="Progress", value=progress, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as exc:
            logger.exception("Card fusion failed.")
            for child in self.view.children:
                child.disabled = False
            await interaction.edit_original_response(view=self.view)
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


class CardFusionView(discord.ui.View):
    def __init__(self, owner_id: int, keeper_pool: list[dict], sacrifice_pool: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.keeper_pool = keeper_pool
        self.sacrifice_pool = sacrifice_pool
        self.keeper_id: str | None = None
        self.sacrifice_id: str | None = None

        if keeper_pool and sacrifice_pool:
            self.keeper_select = FusionKeeperSelect()
            self.sacrifice_select = FusionSacrificeSelect()
            self.confirm_btn = FusionConfirmButton()
            self.add_item(self.keeper_select)
            self.add_item(self.sacrifice_select)
            self.add_item(self.confirm_btn)
            self._rebuild_options()

        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", row=3)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_hub(interaction, self.owner_id)

    def _rebuild_options(self) -> None:
        self.keeper_select.options.clear()
        self.sacrifice_select.options.clear()

        for p in self.keeper_pool:
            if str(p["id"]) == str(self.sacrifice_id):
                continue
            self.keeper_select.options.append(
                discord.SelectOption(
                    label=f"{p['name']} ({p['overall']} OVR)",
                    value=str(p["id"]),
                    description=f"Lvl {p['level']} - {p['position']}",
                    default=(str(p["id"]) == str(self.keeper_id)),
                )
            )

        for p in self.sacrifice_pool:
            if str(p["id"]) == str(self.keeper_id):
                continue
            self.sacrifice_select.options.append(
                discord.SelectOption(
                    label=f"{p['name']} ({p['overall']} OVR)",
                    value=str(p["id"]),
                    description=f"Lvl {p['level']} - {p['position']}",
                    default=(str(p["id"]) == str(self.sacrifice_id)),
                )
            )

        self.keeper_select.disabled = len(self.keeper_select.options) == 0
        self.sacrifice_select.disabled = len(self.sacrifice_select.options) == 0
        self.confirm_btn.disabled = not (self.keeper_id and self.sacrifice_id)


# --- 3. EVOLUTIONS SUB VIEW SYSTEM ---

async def show_evols_menu(interaction: discord.Interaction, owner_id: int, preselected_card_id: str | None = None):
    db = await get_client()
    
    # 1. Fetch roster
    roster_res = await db.table("player_cards").select("id, name, overall").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    if not roster:
        embed = discord.Embed(title="🧬 Evolutions Hub", description="No players in your roster to evolve.", color=0x00FF87)
        view = EvolutionsSubView(owner_id, None, None, roster)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
        return

    # Choose selected card
    target_card_id = preselected_card_id or roster[0]["id"]
    
    card_res = await db.table("player_cards").select("*").eq("id", target_card_id).maybe_single().execute()
    card = card_res.data if card_res else None

    # Fetch active evolution for the card
    evo_res = await db.table("active_evolutions").select("*").eq("card_id", target_card_id).maybe_single().execute()
    evo = evo_res.data if evo_res else None

    embed = discord.Embed(
        title=f"🧬 Evolutions: {card['name']}",
        description=f"Current Rating: **{card['overall']} OVR**",
        color=0x00FF87
    )

    if evo:
        track = EVOLUTION_TRACKS[evo["evolution_id"]]
        embed.add_field(
            name=f"Active Track: {track['name']}",
            value=f"• Progress: **{evo['current_progress']}/{evo['target_goal']} matches played**\n• Reward: `+{track['reward_val']} {track['reward_stat'].upper()}`",
            inline=False
        )
    else:
        embed.add_field(name="Status", value="❌ No active evolution track. Select a track below to start.", inline=False)

    view = EvolutionsSubView(owner_id, card, evo, roster)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class EvolutionsSubView(discord.ui.View):
    def __init__(self, owner_id: int, card: dict | None, active_evo: dict | None, roster: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.card = card
        self.active_evo = active_evo

        # 1. Player Selector dropdown
        if roster:
            player_options = [
                discord.SelectOption(label=p["name"], description=f"{p['overall']} OVR", value=p["id"], default=(card and p["id"] == card["id"]))
                for p in roster[:25]
            ]
            player_sel = discord.ui.Select(placeholder="Select card...", options=player_options, row=0)
            player_sel.callback = self.player_select_callback
            self.add_item(player_sel)

        # 2. Add Start options (if no active evo and card exists)
        if card and not active_evo:
            evo_options = [
                discord.SelectOption(label=track["name"], description=f"Goal: Play {track['goal']} matches for +{track['reward_val']} {track['reward_stat'].upper()}", value=k)
                for k, track in EVOLUTION_TRACKS.items()
            ]
            evo_sel = discord.ui.Select(placeholder="Choose evolution path...", options=evo_options, row=1)
            evo_sel.callback = self.start_evo_callback
            self.add_item(evo_sel)

        # 3. Add Claim reward button (if completed)
        if active_evo and active_evo["current_progress"] >= active_evo["target_goal"]:
            claim_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="Claim Evolution Reward", row=2)
            claim_btn.callback = self.claim_reward_callback
            self.add_item(claim_btn)

        # 4. Back button
        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", row=2)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction):
        await show_hub(interaction, self.owner_id)

    async def player_select_callback(self, interaction: discord.Interaction):
        card_id = interaction.data["values"][0]
        await show_evols_menu(interaction, self.owner_id, preselected_card_id=card_id)

    async def start_evo_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            evo_key = interaction.data["values"][0]
            track = EVOLUTION_TRACKS[evo_key]

            # Insert active evolutions record
            await db.table("active_evolutions").insert({
                "card_id": self.card["id"],
                "evolution_id": evo_key,
                "target_metric": track["metric"],
                "target_goal": track["goal"],
                "current_progress": 0
            }).execute()

            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Track Registered!**\n\n"
                    f"**{self.card['name']}** is now tracking: **{track['name']}**.\n"
                    f"• Objective: Play **{track['goal']} matches** with this player in your squad."
                ),
                ephemeral=True
            )
            await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card["id"])

        except Exception as e:
            logger.exception("Failed starting evolution track.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    async def claim_reward_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            res = await db.rpc("claim_evolution_reward", {
                "p_owner_id": self.owner_id,
                "p_evo_id": self.active_evo["id"],
            }).execute()
            result = res.data or {}
            track = EVOLUTION_TRACKS[self.active_evo["evolution_id"]]

            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Completed!**\n\n"
                    f"Claimed rewards for **{self.card['name']}**:\n"
                    f"• **+{track['reward_val']} {track['reward_stat'].upper()}**\n"
                    f"• New Overall: **{result.get('new_ovr', self.card['overall'])} OVR**!"
                ),
                ephemeral=True
            )
            await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card["id"])

        except Exception as e:
            logger.exception("Failed claiming evolution reward.")
            await interaction.followup.send(embed=error_embed(_api_message(e)), ephemeral=True)


# --- 3. SKILL ALLOCATION SUB VIEW SYSTEM ---

async def show_skills_menu(interaction: discord.Interaction, owner_id: int, preselected_card_id: str | None = None):
    db = await get_client()
    roster_res = await db.table("player_cards").select("id, name, overall").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    if not roster:
        embed = discord.Embed(title="⭐ Skill Allocation", description="No roster players found.", color=0x00FF87)
        view = SkillsSubView(owner_id, None, roster)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
        return

    target_card_id = preselected_card_id or roster[0]["id"]
    card_res = await db.table("player_cards").select("*").eq("id", target_card_id).maybe_single().execute()
    card = card_res.data if card_res else None

    embed = discord.Embed(
        title=f"⭐ Allocate Skills: {card['name']}",
        description=(
            f"Available Skill Points: **{card.get('skill_points', 0)}**\n\n"
            f"⚡ **PAC**: `{card.get('pac', 50)}` | "
            f"🎯 **SHO**: `{card.get('sho', 50)}` | "
            f"🧠 **PAS**: `{card.get('pas', 50)}`\n"
            f"👟 **DRI**: `{card.get('dri', 50)}` | "
            f"🛡️ **DEF**: `{card.get('def', 50)}` | "
            f"💪 **PHY**: `{card.get('phy', 50)}`"
        ),
        color=0x00FF87
    )

    view = SkillsSubView(owner_id, card, roster)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class SkillsSubView(discord.ui.View):
    def __init__(self, owner_id: int, card: dict | None, roster: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.card = card

        # 1. Player Selector dropdown
        if roster:
            player_options = [
                discord.SelectOption(label=p["name"], description=f"{p['overall']} OVR", value=p["id"], default=(card and p["id"] == card["id"]))
                for p in roster[:25]
            ]
            player_sel = discord.ui.Select(placeholder="Select card...", options=player_options, row=0)
            player_sel.callback = self.player_select_callback
            self.add_item(player_sel)

        # 2. Add stat allocation buttons if card has points
        if card:
            has_points = card.get("skill_points", 0) > 0
            stats = [("pac", "PAC +1"), ("sho", "SHO +1"), ("pas", "PAS +1"), ("dri", "DRI +1"), ("def", "DEF +1"), ("phy", "PHY +1")]
            for idx, (col, label) in enumerate(stats):
                row = 1 if idx < 3 else 2
                btn = SkillPointButton(card["id"], col, label, has_points, owner_id, row)
                self.add_item(btn)

        # 3. Back button
        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", row=3)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction):
        await show_hub(interaction, self.owner_id)

    async def player_select_callback(self, interaction: discord.Interaction):
        card_id = interaction.data["values"][0]
        await show_skills_menu(interaction, self.owner_id, preselected_card_id=card_id)


class SkillPointButton(discord.ui.Button):
    def __init__(self, card_id: str, col: str, label: str, active: bool, owner_id: int, row: int) -> None:
        super().__init__(style=discord.ButtonStyle.primary, label=label, disabled=not active, row=row)
        self.card_id = card_id
        self.col = col
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            await db.rpc("allocate_skill_point", {
                "p_owner_id": self.owner_id,
                "p_card_id": self.card_id,
                "p_stat": self.col,
            }).execute()

            await show_skills_menu(interaction, self.owner_id, preselected_card_id=self.card_id)

        except Exception as exc:
            logger.exception("Failed to allocate skill point.")
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


# --- COG INTERFACE ---

class DevelopmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="development", description="Development Center: stat drills, card fusion, evolutions, and skill points.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def development(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None

            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            embed = discord.Embed(
                title="🏋️‍♂️ Development Center",
                description=f"Welcome to **{player['club_name']}** development center. Train stats, fuse duplicate cards, evolve playstyles, or allocate skill points.",
                color=0x00FF87
            )
            view = DevelopmentHubView(interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load Development Center.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DevelopmentCog(bot))
