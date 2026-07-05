# apps/discord_bot/cogs/development_cog.py
from __future__ import annotations
import logging
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from economy import GameConfig, compute_new_overall
from training import calculate_xp_gain
from player_engine import calculate_level, calculate_contract_renewal_cost
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

DRILL_DISPLAY_NAMES = {
    "cardio": "🏃‍♂️ Cardio Drill",
    "tactics": "🧠 Tactical Drill",
    "match_prep": "📋 Match Prep Drill"
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

# --- Navigation / Switch helpers ---
async def show_hub(interaction: discord.Interaction, owner_id: int):
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data
    
    embed = discord.Embed(
        title="🏋️‍♂️ Development Center",
        description=f"Welcome to **{player['club_name']}** development center. Select a sub-menu to train cards, evolve playstyles, or allocate stat points.",
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

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🏋️ Training Drills", custom_id="hub_drills")
    async def training_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_training_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🧬 Evolutions", custom_id="hub_evos")
    async def evolutions_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_evols_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⭐ Allocate Skills", custom_id="hub_skills")
    async def skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_skills_menu(interaction, self.owner_id)


# --- 1. TRAINING SUB VIEW SYSTEM ---

async def show_training_menu(interaction: discord.Interaction, owner_id: int):
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data
    max_slots = player.get("training_slots_max", 2)

    drills_res = await db.table("active_training").select("*, player_cards(*)").eq("club_id", owner_id).execute()
    drills = drills_res.data or []

    roster_res = await db.table("player_cards").select("*").eq("owner_id", owner_id).execute()
    roster = roster_res.data or []

    training_card_ids = {d["card_id"] for d in drills}
    eligible_players = [p for p in roster if p["id"] not in training_card_ids]

    embed = discord.Embed(
        title="🏋️ Training Hub",
        description=f"Slots configuration: **{len(drills)}/{max_slots}** active.",
        color=0x00FF87
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    for idx in range(max_slots):
        if idx < len(drills):
            d = drills[idx]
            card_data = d.get("player_cards") or {}
            card_name = card_data.get("name", "Unknown Player")
            drill_name = DRILL_DISPLAY_NAMES.get(d["drill_type"], d["drill_type"].capitalize())
            end_time = datetime.datetime.fromisoformat(d["end_time"].replace("Z", "+00:00"))
            
            if end_time <= now:
                status_str = "🟢 **Completed!** (Claim reward below)"
            else:
                end_unix = int(end_time.timestamp())
                status_str = f"⏳ **Training...** (Ends <t:{end_unix}:R>)"
                
            embed.add_field(
                name=f"Slot {idx + 1}: {card_name}",
                value=f"• Drill: **{drill_name}**\n• Status: {status_str}",
                inline=False
            )
        else:
            embed.add_field(
                name=f"Slot {idx + 1}: Empty",
                value="• *Assign a player to a drill to start training.*",
                inline=False
            )

    view = TrainingSubView(owner_id, max_slots, drills, eligible_players)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class TrainingSubView(discord.ui.View):
    def __init__(self, owner_id: int, max_slots: int, active_drills: list[dict], eligible_players: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.eligible_players = eligible_players
        self.max_slots = max_slots
        self.active_drills = active_drills

        now = datetime.datetime.now(datetime.timezone.utc)

        # Claim buttons
        for d in active_drills:
            end_time = datetime.datetime.fromisoformat(d["end_time"].replace("Z", "+00:00"))
            if end_time <= now:
                card_data = d.get("player_cards") or {}
                card_name = card_data.get("name", "Unknown Player")
                claim_btn = ClaimDrillButton(d["id"], d["card_id"], card_name, d["drill_type"], owner_id)
                self.add_item(claim_btn)

        # Start drill button
        if len(active_drills) < max_slots:
            start_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="Start Drill", custom_id="tr_start_drill")
            start_btn.callback = self.start_drill_callback
            self.add_item(start_btn)

        # Back button
        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", custom_id="tr_back_hub")
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction):
        await show_hub(interaction, self.owner_id)

    async def start_drill_callback(self, interaction: discord.Interaction):
        if not self.eligible_players:
            await interaction.response.send_message(
                embed=error_embed("You have no eligible players. All roster cards are already training!"),
                ephemeral=True
            )
            return

        # Show selection dropdowns in-place
        embed = discord.Embed(
            title="🏋️‍♂️ Select Drill Details",
            description="Choose a player card and the training drill type from the dropdown lists:",
            color=0x00FF87
        )
        view = StartDrillFormView(self.owner_id, self.eligible_players)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)


class ClaimDrillButton(discord.ui.Button):
    def __init__(self, training_id: str, card_id: str, card_name: str, drill: str, owner_id: int) -> None:
        super().__init__(style=discord.ButtonStyle.success, label=f"Claim {card_name}")
        self.training_id = training_id
        self.card_id = card_id
        self.card_name = card_name
        self.drill = drill
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            card_res = await db.table("player_cards").select("*").eq("id", self.card_id).maybe_single().execute()
            card = card_res.data
            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
                return

            config = GameConfig()
            curr_lvl = card.get("level", 1)
            xp_gained = calculate_xp_gain(self.drill, curr_lvl, config)

            curr_xp = card.get("xp", 0)
            new_xp = curr_xp + xp_gained
            new_level = curr_lvl
            
            # Level up progression loop
            leveled_up = False
            points_earned = 0
            while True:
                needed = int(100 * (1.12 ** (new_level - 1)))
                if new_xp >= needed:
                    new_xp -= needed
                    new_level += 1
                    points_earned += 3
                    leveled_up = True
                else:
                    break

            if leveled_up:
                new_ovr = compute_new_overall(new_level, card["base_rating"], card["rarity"])
                new_pts = card.get("skill_points", 0) + points_earned
                await db.table("player_cards").update({
                    "xp": new_xp,
                    "level": new_level,
                    "overall": new_ovr,
                    "skill_points": new_pts
                }).eq("id", self.card_id).execute()
            else:
                await db.table("player_cards").update({
                    "xp": new_xp
                }).eq("id", self.card_id).execute()

            await db.table("active_training").delete().eq("id", self.training_id).execute()

            # Refresh view
            await interaction.followup.send(
                embed=success_embed(
                    f"🏆 **Training Completed!**\n\n"
                    f"**{self.card_name}** completed the **{DRILL_DISPLAY_NAMES.get(self.drill, self.drill)}**.\n"
                    f"• XP Gained: `+{xp_gained} XP`\n"
                    f"• Skill Points Earned: `+{points_earned if leveled_up else 0}`"
                    + (f"\n🎉 **LEVEL UP!** Now Level **{new_level}**!" if leveled_up else "")
                ),
                ephemeral=True
            )
            # Re-render training hub
            await show_training_menu(interaction, self.owner_id)

        except Exception as e:
            logger.exception("Failed claiming training reward.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)


class StartDrillFormView(discord.ui.View):
    def __init__(self, owner_id: int, eligible_players: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.selected_card_id = None
        self.selected_drill = None
        self.eligible_players = eligible_players

        # Player Select
        player_options = []
        for p in eligible_players[:25]:
            player_options.append(
                discord.SelectOption(
                    label=p["name"],
                    description=f"{p['overall']} OVR | Lvl {p['level']} | {p['position']}",
                    value=p["id"]
                )
            )
        self.player_select = discord.ui.Select(
            placeholder="Select a player to train...",
            min_values=1,
            max_values=1,
            options=player_options,
            row=0
        )
        self.player_select.callback = self.player_select_callback
        self.add_item(self.player_select)

        # Drill Select
        config = GameConfig()
        drill_options = []
        for d, cost in config.drill_costs.items():
            duration = config.drill_durations.get(d, 1.0)
            xp_reward = config.drill_xp.get(d, 0)
            name = DRILL_DISPLAY_NAMES.get(d, d.capitalize())
            drill_options.append(
                discord.SelectOption(
                    label=name,
                    description=f"Cost: 🪙 {cost} | Duration: {duration}h | +{xp_reward} Base XP",
                    value=d
                )
            )
        self.drill_select = discord.ui.Select(
            placeholder="Select drill type...",
            min_values=1,
            max_values=1,
            options=drill_options,
            row=1
        )
        self.drill_select.callback = self.drill_select_callback
        self.add_item(self.drill_select)

        # Confirm Button
        self.confirm_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="Start Training", disabled=True, row=2)
        self.confirm_btn.callback = self.confirm_callback
        self.add_item(self.confirm_btn)

        # Cancel Button
        cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", row=2)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def player_select_callback(self, interaction: discord.Interaction):
        self.selected_card_id = self.player_select.values[0]
        self.update_confirm_btn()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    async def drill_select_callback(self, interaction: discord.Interaction):
        self.selected_drill = self.drill_select.values[0]
        self.update_confirm_btn()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    def update_confirm_btn(self):
        self.confirm_btn.disabled = not (self.selected_card_id and self.selected_drill)

    async def cancel_callback(self, interaction: discord.Interaction):
        await show_training_menu(interaction, self.owner_id)

    async def confirm_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            config = GameConfig()
            cost = config.drill_costs.get(self.selected_drill, 50)
            duration = config.drill_durations.get(self.selected_drill, 1.0)

            res = await db.rpc("process_training_start", {
                "p_club_id": self.owner_id,
                "p_card_id": self.selected_card_id,
                "p_drill": self.selected_drill,
                "p_cost": cost,
                "p_duration_hours": duration
            }).execute()

            if res.data:
                selected_p = next(p for p in self.eligible_players if p["id"] == self.selected_card_id)
                await interaction.followup.send(
                    embed=success_embed(
                        f"🏋️‍♂️ **Training Drill Started!**\n\n"
                        f"Sent **{selected_p['name']}** to **{DRILL_DISPLAY_NAMES.get(self.selected_drill, self.selected_drill)}**.\n"
                        f"• Cost: `🪙 {cost} coins`"
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(embed=error_embed("Failed to start training session. Check coins availability."), ephemeral=True)

            # Re-render training hub
            await show_training_menu(interaction, self.owner_id)

        except Exception as e:
            logger.exception("Failed starting training.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)


# --- 2. EVOLUTIONS SUB VIEW SYSTEM ---

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
    card = card_res.data

    # Fetch active evolution for the card
    evo_res = await db.table("active_evolutions").select("*").eq("card_id", target_card_id).maybe_single().execute()
    evo = evo_res.data

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
                "class_type": "standard", # default
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
            track = EVOLUTION_TRACKS[self.active_evo["evolution_id"]]

            # Update core attributes
            stat_col = track["reward_stat"] # pac, sho, or def
            if stat_col == "def":
                stat_col = "def" # database column name is def
            
            new_stat_val = self.card[stat_col] + track["reward_val"]
            new_overall = self.card["overall"] + 1

            # Update DB
            await db.table("player_cards").update({
                stat_col: new_stat_val,
                "overall": new_overall
            }).eq("id", self.card["id"]).execute()

            # Delete evolution record
            await db.table("active_evolutions").delete().eq("id", self.active_evo["id"]).execute()

            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Completed!**\n\n"
                    f"Claimed rewards for **{self.card['name']}**:\n"
                    f"• **+{track['reward_val']} {track['reward_stat'].upper()}**\n"
                    f"• New Overall: **{new_overall} OVR**!"
                ),
                ephemeral=True
            )
            await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card["id"])

        except Exception as e:
            logger.exception("Failed claiming evolution reward.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)


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
    card = card_res.data

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

            card_res = await db.table("player_cards").select("*").eq("id", self.card_id).maybe_single().execute()
            card = card_res.data
            if not card or card.get("skill_points", 0) <= 0:
                return

            new_val = card[self.col] + 1
            if new_val > 99:
                return

            # Update DB
            await db.table("player_cards").update({
                self.col: new_val,
                "skill_points": card["skill_points"] - 1
            }).eq("id", self.card_id).execute()

            # Refresh view in-place
            await show_skills_menu(interaction, self.owner_id, preselected_card_id=self.card_id)

        except Exception as e:
            logger.exception("Failed to allocate skill point.")


# --- COG INTERFACE ---

class DevelopmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="development", description="Unified Development Center: Manage training drills, evolutions, and allocate skill points.")
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
                description=f"Welcome to **{player['club_name']}** development center. Select a sub-menu to train cards, evolve playstyles, or allocate stat points.",
                color=0x00FF87
            )
            view = DevelopmentHubView(interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load Development Center.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DevelopmentCog(bot))
