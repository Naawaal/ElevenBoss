# apps/discord_bot/cogs/training_cog.py
from __future__ import annotations
import logging
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from economy import GameConfig, compute_new_overall
from training import calculate_xp_gain
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

DRILL_DISPLAY_NAMES = {
    "cardio": "🏃‍♂️ Cardio Drill",
    "tactics": "🧠 Tactical Drill",
    "match_prep": "📋 Match Prep Drill"
}

class StartDrillFormView(discord.ui.View):
    def __init__(self, owner_id: int, eligible_players: list[dict]) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.selected_card_id = None
        self.selected_drill = None
        self.eligible_players = eligible_players

        # 1. Player Select Select Menu
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
            placeholder="Select a player card to train...",
            min_values=1,
            max_values=1,
            options=player_options,
            row=0
        )
        self.player_select.callback = self.player_select_callback
        self.add_item(self.player_select)

        # 2. Drill Select Menu
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
            placeholder="Select training drill type...",
            min_values=1,
            max_values=1,
            options=drill_options,
            row=1
        )
        self.drill_select.callback = self.drill_select_callback
        self.add_item(self.drill_select)

        # 3. Confirm Button
        self.confirm_btn = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Start Training",
            disabled=True,
            row=2
        )
        self.confirm_btn.callback = self.confirm_callback
        self.add_item(self.confirm_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another player.", ephemeral=True)
            return False
        return True

    async def player_select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_card_id = self.player_select.values[0]
        self.update_confirm_button_state()
        await interaction.response.edit_message(view=self)

    async def drill_select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_drill = self.drill_select.values[0]
        self.update_confirm_button_state()
        await interaction.response.edit_message(view=self)

    def update_confirm_button_state(self) -> None:
        if self.selected_card_id and self.selected_drill:
            self.confirm_btn.disabled = False
        else:
            self.confirm_btn.disabled = True

    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            config = GameConfig()

            # Retrieve costs
            cost = config.drill_costs.get(self.selected_drill, 50)
            duration = config.drill_durations.get(self.selected_drill, 1.0)

            # Call RPC
            res = await db.rpc("process_training_start", {
                "p_club_id": self.owner_id,
                "p_card_id": self.selected_card_id,
                "p_drill": self.selected_drill,
                "p_cost": cost,
                "p_duration_hours": duration
            }).execute()

            if res.data:
                # Disable all components in view
                for child in self.children:
                    child.disabled = True
                await interaction.edit_original_response(view=self)

                selected_p = next(p for p in self.eligible_players if p["id"] == self.selected_card_id)
                drill_name = DRILL_DISPLAY_NAMES.get(self.selected_drill, self.selected_drill)

                await interaction.followup.send(
                    embed=success_embed(
                        f"🏋️‍♂️ **Training Drill Started!**\n\n"
                        f"Sent **{selected_p['name']}** to **{drill_name}**.\n"
                        f"• Cost: `🪙 {cost} coins`\n"
                        f"• Duration: `{duration} hours`"
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(embed=error_embed("Failed to start training session."), ephemeral=True)

        except Exception as e:
            logger.exception("Failed to execute process_training_start RPC.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

class ClaimTrainingButton(discord.ui.Button):
    def __init__(self, training_id: str, card_id: str, card_name: str, drill: str, owner_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label=f"Claim {card_name}",
            custom_id=f"claim_drill_{training_id}"
        )
        self.training_id = training_id
        self.card_id = card_id
        self.card_name = card_name
        self.drill = drill
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This action belongs to another player.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player card details
            card_res = await db.table("player_cards").select("*").eq("id", self.card_id).maybe_single().execute()
            card = card_res.data if card_res else None

            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found on roster."), ephemeral=True)
                return

            # 2. Calculate XP gain
            config = GameConfig()
            curr_lvl = card.get("level", 1)
            xp_gained = calculate_xp_gain(self.drill, curr_lvl, config)

            curr_xp = card.get("xp", 0)
            new_xp = curr_xp + xp_gained
            new_level = curr_lvl
            
            # Level up threshold: 100 * level
            leveled_up = False
            while True:
                needed = new_level * 100
                if new_xp >= needed:
                    new_xp -= needed
                    new_level += 1
                    leveled_up = True
                else:
                    break

            # 3. Save updates
            if leveled_up:
                new_ovr = compute_new_overall(new_level, card["base_rating"], card["rarity"])
                await db.table("player_cards").update({
                    "xp": new_xp,
                    "level": new_level,
                    "overall": new_ovr
                }).eq("id", self.card_id).execute()
            else:
                await db.table("player_cards").update({
                    "xp": new_xp
                }).eq("id", self.card_id).execute()

            # 4. Remove active training record
            await db.table("active_training").delete().eq("id", self.training_id).execute()

            # 5. Disable self in view
            view = self.view
            if view:
                # Remove this claimed button
                view.remove_item(self)
                await interaction.edit_original_response(view=view)

            # 6. Response
            lvl_up_text = f"\n🎉 **LEVEL UP!** **{self.card_name}** is now **Level {new_level}**!" if leveled_up else ""
            await interaction.followup.send(
                embed=success_embed(
                    f"🏆 **Training Completed!**\n\n"
                    f"**{self.card_name}** completed the **{DRILL_DISPLAY_NAMES.get(self.drill, self.drill)}**.\n"
                    f"• Gained XP: `+{xp_gained} XP`\n"
                    f"• Current XP: `{new_xp}/{new_level*100} XP`"
                    f"{lvl_up_text}"
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.exception("Failed to claim training reward.")
            await interaction.followup.send(embed=error_embed(f"An error occurred while claiming: {str(e)}"), ephemeral=True)

class TrainingHubView(discord.ui.View):
    def __init__(self, owner_id: int, max_slots: int, active_drills: list[dict], eligible_players: list[dict]) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id

        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Add Claim buttons for completed drills
        completed_drills = []
        for d in active_drills:
            end_time = datetime.datetime.fromisoformat(d["end_time"].replace("Z", "+00:00"))
            if end_time <= now:
                completed_drills.append(d)
                # Create a claim button
                card_data = d.get("player_cards") or {}
                card_name = card_data.get("name", "Unknown Player")
                claim_btn = ClaimTrainingButton(
                    training_id=d["id"],
                    card_id=d["card_id"],
                    card_name=card_name,
                    drill=d["drill_type"],
                    owner_id=owner_id
                )
                self.add_item(claim_btn)

        # 2. Add "Start Drill" button if slots are available
        total_active_and_completed = len(active_drills)
        if total_active_and_completed < max_slots:
            start_btn = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Start Drill",
                custom_id="start_drill_btn"
            )
            start_btn.callback = self.start_drill_callback
            self.add_item(start_btn)
            
        self.eligible_players = eligible_players

    async def start_drill_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This button belongs to another player.", ephemeral=True)
            return

        if not self.eligible_players:
            await interaction.response.send_message(
                embed=error_embed("You have no eligible players. All owned player cards might already be in active training drills!"),
                ephemeral=True
            )
            return

        # Spawns start drill select view
        embed = discord.Embed(
            title="🏋️‍♂️ Select Drill Details",
            description="Choose a player card and the training drill type from the dropdown lists:",
            color=0x00FF87
        )
        view = StartDrillFormView(self.owner_id, self.eligible_players)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class TrainingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="training-hub", description="Manage training slots, start drills, and claim completed XP rewards.")
    @app_commands.check(ensure_registered)
    async def training_hub(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch club metadata
            player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None
            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            max_slots = player.get("training_slots_max", 2)

            # 2. Fetch active training drills
            drills_res = await db.table("active_training").select("*, player_cards(*)").eq("club_id", interaction.user.id).execute()
            drills = drills_res.data or []

            # 3. Fetch all owned cards
            roster_res = await db.table("player_cards").select("*").eq("owner_id", interaction.user.id).execute()
            roster = roster_res.data or []

            # Identify cards already in training
            training_card_ids = {d["card_id"] for d in drills}
            
            # Eligible players to start a drill (not currently training)
            eligible_players = [p for p in roster if p["id"] not in training_card_ids]

            # 4. Render Hub Embed
            embed = discord.Embed(
                title=f"🏋️‍♂️ Training Hub: {player['club_name']}",
                description=f"Manage and train your player cards. Slots: **{len(drills)}/{max_slots}**",
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
                        status_str = "🟢 **Completed!** (Ready to claim)"
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

            view = TrainingHubView(interaction.user.id, max_slots, drills, eligible_players)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load training hub.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrainingCog(bot))
