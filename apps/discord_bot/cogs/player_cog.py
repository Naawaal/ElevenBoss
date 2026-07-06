# apps/discord_bot/cogs/player_cog.py
from __future__ import annotations
import logging
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from player_engine import GameConfig, calculate_contract_renewal_cost, format_potential_display
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

EVOLUTION_TRACKS = {
    "pace_boost": {
        "name": "⚡ Pace Masterclass",
        "reward_stat": "pac",
        "reward_val": 5
    },
    "shooting_star": {
        "name": "🎯 Shooting Star",
        "reward_stat": "sho",
        "reward_val": 5
    },
    "def_wall": {
        "name": "🧱 Defensive Wall",
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

class PlayerProfileView(discord.ui.View):
    def __init__(self, card_id: str, owner_id: int, card_name: str, has_evo: bool, can_claim: bool, renewal_cost: int, card_data: dict) -> None:
        super().__init__(timeout=900)
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

        # Level Up Button (if skill points are available)
        if card_data.get("skill_points", 0) > 0:
            self.lvl_btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Level Up ({card_data['skill_points']} pts)",
                custom_id="level_up_profile"
            )
            self.lvl_btn.callback = self.level_up_callback
            self.add_item(self.lvl_btn)

    async def renew_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            card_res = await db.table("player_cards").select("overall").eq("id", self.card_id).maybe_single().execute()
            ovr = card_res.data["overall"] if (card_res and card_res.data) else 50
            cost = calculate_contract_renewal_cost(ovr, GameConfig())

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
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return
        # Cross-cog routing to Development Evolutions Sub-menu
        from apps.discord_bot.cogs.development_cog import show_evols_menu
        await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card_id)

    async def level_up_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return
        # Cross-cog routing to Development Skill Allocation Sub-menu
        from apps.discord_bot.cogs.development_cog import show_skills_menu
        await show_skills_menu(interaction, self.owner_id, preselected_card_id=self.card_id)

    async def claim_evo_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            evo_res = await db.table("active_evolutions").select("*").eq("card_id", self.card_id).maybe_single().execute()
            evo = evo_res.data if evo_res else None
            if not evo or evo["current_progress"] < evo["target_goal"]:
                await interaction.followup.send(embed=error_embed("Evolution is not complete yet."), ephemeral=True)
                return

            track = EVOLUTION_TRACKS[evo["evolution_id"]]

            card_res = await db.table("player_cards").select(
                "id, pac, sho, pas, dri, def, phy"
            ).eq("id", self.card_id).maybe_single().execute()
            card = card_res.data if card_res else {}

            # #region agent log
            from apps.discord_bot.cogs.development_cog import (
                _debug_evolution_log,
                _evolution_claim_diagnostics,
            )
            diag = _evolution_claim_diagnostics(card, evo)
            _debug_evolution_log(
                "player_cog.py:claim_evo_callback:pre_rpc",
                "evolution claim attempt",
                diag,
                "A",
            )
            # #endregion

            res = await db.rpc("claim_evolution_reward", {
                "p_owner_id": self.owner_id,
                "p_evo_id": evo["id"],
            }).execute()
            result = res.data or {}
            new_overall = result.get("new_ovr", 0)
            applied = result.get("reward", track["reward_val"])
            reward_stat = result.get("stat", track["reward_stat"].upper())

            # #region agent log
            _debug_evolution_log(
                "player_cog.py:claim_evo_callback:post_rpc",
                "evolution claim succeeded",
                {"result": result, "applied_reward": applied},
                "A",
            )
            # #endregion

            self.evo_btn.disabled = True
            await interaction.edit_original_response(view=self)

            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Completed!**\n\n"
                    f"**{self.card_name}** achieved the evolution goals!\n"
                    f"• Reward: `+{applied} {reward_stat}`\n"
                    f"• Overall Rating: **{new_overall} OVR**"
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.exception("Failed to claim evolution rewards.")
            from apps.discord_bot.cogs.development_cog import _api_message, _debug_evolution_log
            # #region agent log
            _debug_evolution_log(
                "player_cog.py:claim_evo_callback:error",
                "evolution claim failed",
                {"error": _api_message(e), "owner_id": self.owner_id, "card_id": self.card_id},
                "E",
            )
            # #endregion
            await interaction.followup.send(embed=error_embed(_api_message(e)), ephemeral=True)


class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="player-profile", description="View exhaustive attributes, contracts, and progression for a player.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    @app_commands.autocomplete(player_id=player_id_autocomplete)
    async def player_profile(self, interaction: discord.Interaction, player_id: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player card details
            card_res = await db.table("player_cards").select("*").eq("id", player_id).maybe_single().execute()
            card = card_res.data if card_res else None
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
            evo = evo_res.data if evo_res else None
            
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
                title=f"📋 Roster Profile: {card['name']}",
                description=(
                    f"Level **{level}** {card['rarity']} Player Card (OVR **{card['overall']}**)\n"
                    f"*Potential (POT) is the maximum OVR this player can reach through training.*"
                ),
                color=0x00FF87
            )
            embed.add_field(name="📋 Role Style", value=card.get("role", "Balanced"), inline=True)
            embed.add_field(
                name="🎂 Age / Potential",
                value=format_potential_display(card.get("potential"), card.get("age", 25)),
                inline=True,
            )
            embed.add_field(name="😊 Morale Rating", value=f"Morale **{card.get('morale', 80)}/100**", inline=True)
            embed.add_field(name="📈 Level & Experience Progression", value=xp_bar, inline=False)
            
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
            embed.add_field(name="⭐ Skill Points Available", value=f"**{card.get('skill_points', 0)}**", inline=False)

            if has_evo:
                track = EVOLUTION_TRACKS.get(evo["evolution_id"], {"name": "Unknown Evolution"})
                progress_str = f"📈 **Evolution Track**: {track['name']} ({evo['current_progress']}/{evo['target_goal']} matches)"
                embed.add_field(name="🧬 Ongoing Evolution Track", value=progress_str, inline=False)

            view = PlayerProfileView(player_id, interaction.user.id, card["name"], has_evo, can_claim, renewal_cost, card)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load player profile.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlayerCog(bot))
