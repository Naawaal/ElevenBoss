# apps/discord_bot/cogs/player_cog.py
from __future__ import annotations
import logging
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from player_engine import (
    GameConfig,
    calculate_contract_renewal_cost,
    format_lifecycle_display,
    can_renew_contract,
    EVOLUTION_TRACKS,
    TIER_NAMES,
    fatigue_bar,
    sp_to_mentor_units,
    xp_progress,
)
from apps.discord_bot.core.card_payload import effective_card_age
from apps.discord_bot.cogs.development_cog import (
    make_match_progress_bar,
    _evo_played,
    _evo_required,
    _is_active_evo,
    evolution_start_gate_message,
    fetch_evolution_hub_status,
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.middleware.match_lock import assert_not_in_match
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.core.economy_rpc import get_game_config_int
from economy.wages import contract_blocks_xi, contract_in_grace

logger = logging.getLogger(__name__)

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
    return xp_progress(total_xp)

def make_xp_bar(current: int, needed: int) -> str:
    total_bars = 10
    filled = min(total_bars, int((current / needed) * total_bars))
    empty = total_bars - filled
    return f"`[{'█' * filled}{'░' * empty}]` ({current}/{needed} XP)"


class PlayerProfileView(discord.ui.View):
    def __init__(self, card_id: str, owner_id: int, card_name: str, has_evo: bool, can_claim: bool, renewal_cost: int, card_data: dict, renew_allowed: bool = True) -> None:
        super().__init__(timeout=900)
        self.card_id = card_id
        self.owner_id = owner_id
        self.card_name = card_name

        # Renew Contract Button
        self.renew_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=f"Renew Contract (🪙 {renewal_cost})",
            custom_id="renew_contract_profile",
            disabled=not renew_allowed,
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
                label=f"Allocate Skills ({card_data['skill_points']} pts)",
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
            extension_days = await get_game_config_int(db, "contract_renewal_days", 7)

            res = await db.rpc("renew_contract", {
                "p_club_id": self.owner_id,
                "p_card_id": self.card_id,
                "p_cost": cost,
                "p_extension_days": extension_days
            }).execute()

            if res.data:
                await interaction.followup.send(
                    embed=success_embed(
                        f"📝 **Contract Renewed!**\n\n"
                        f"Extended **{self.card_name}'s** contract by **{extension_days} days**.\n"
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
        await interaction.response.defer(ephemeral=True)
        db = await get_client()
        hub_status = await fetch_evolution_hub_status(db, self.owner_id)
        gate = evolution_start_gate_message(hub_status)
        if gate:
            await interaction.followup.send(embed=error_embed(gate), ephemeral=True)
            return
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
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            evo_res = await db.table("active_evolutions").select("*").eq("card_id", self.card_id).eq("status", "active").maybe_single().execute()
            evo = evo_res.data if evo_res else None
            if not evo or _evo_played(evo) < _evo_required(evo):
                await interaction.followup.send(embed=error_embed("Evolution is not complete yet."), ephemeral=True)
                return

            track = EVOLUTION_TRACKS[evo["evolution_id"]]

            res = await db.rpc("claim_evolution_reward", {
                "p_owner_id": self.owner_id,
                "p_evo_id": evo["id"],
            }).execute()
            result = res.data or {}
            new_overall = result.get("new_ovr", 0)
            applied = result.get("reward", track["reward_val"])
            reward_stat = result.get("stat", track["reward_stat"].upper())

            payload = await build_player_profile(db, self.card_id, self.owner_id)
            if payload and interaction.message:
                embed, view = payload
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)

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
            from apps.discord_bot.cogs.development_cog import _api_message
            await interaction.followup.send(embed=error_embed(_api_message(e)), ephemeral=True)


async def build_player_profile(
    db,
    player_id: str,
    owner_id: int,
) -> tuple[discord.Embed, PlayerProfileView] | None:
    card_res = await db.table("player_cards").select("*").eq("id", player_id).maybe_single().execute()
    card = card_res.data if card_res else None
    if not card or card["owner_id"] != owner_id:
        return None

    ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", player_id).execute()
    playstyles = [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []
    playstyles_str = ", ".join(playstyles) if playstyles else "None"

    evo_res = await db.table("active_evolutions").select("*").eq("card_id", player_id).eq("status", "active").maybe_single().execute()
    evo = evo_res.data if evo_res else None
    has_evo = _is_active_evo(evo)
    can_claim = has_evo and _evo_played(evo) >= _evo_required(evo)

    level, curr_xp, needed_xp = get_xp_progress(card.get("xp", 0))
    xp_bar = make_xp_bar(curr_xp, needed_xp)

    now = datetime.datetime.now(datetime.timezone.utc)
    expiry_str = card.get("contract_expires_at")
    grace_days = await get_game_config_int(db, "contract_grace_days", 7)
    if expiry_str:
        expiry = datetime.datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        days_left = max(0, (expiry - now).days)
        if contract_blocks_xi(expiry, now, grace_days=grace_days):
            contract_val = (
                f"🚫 **Past grace** — cannot start in XI "
                f"(expired <t:{int(expiry.timestamp())}:D>). Renew or replace."
            )
        elif contract_in_grace(expiry, now, grace_days=grace_days):
            contract_val = (
                f"⚠️ **Grace period** — renew soon "
                f"(expired <t:{int(expiry.timestamp())}:D>)."
            )
        else:
            contract_val = f"⏳ `{days_left} Days` (Expires <t:{int(expiry.timestamp())}:D>)"
    else:
        contract_val = "❌ `No Active Contract`"

    renewal_cost = calculate_contract_renewal_cost(card["overall"], GameConfig())
    card_age = effective_card_age(card)
    renew_allowed = can_renew_contract(card_age)
    embed = discord.Embed(
        title=f"📋 Roster Profile: {card['name']}",
        description=(
            f"Level **{level}** {card['rarity']} Player Card (OVR **{card['overall']}**)\n"
            f"*Potential (POT) is the maximum OVR this player can reach through training.*"
        ),
        color=0x00FF87,
    )
    embed.add_field(name="📋 Role Style", value=card.get("role", "Balanced"), inline=True)
    embed.add_field(
        name="🎂 Age / Lifecycle",
        value=format_lifecycle_display(card_age, card.get("potential")),
        inline=True,
    )
    if card.get("retirement_notified_at") or card_age >= 35:
        embed.add_field(
            name="⚠️ Retirement",
            value="This player will retire at age **36**." if card_age < 36 else "Retiring — cannot renew contract.",
            inline=False,
        )
    embed.add_field(name="😊 Morale Rating", value=f"Morale **{card.get('morale', 80)}/100**", inline=True)
    embed.add_field(name="💪 Fitness", value=fatigue_bar(int(card.get("fatigue", 100))), inline=False)
    if card.get("injury_tier"):
        tier = int(card["injury_tier"])
        days = int(card.get("injury_recovery_days") or 0)
        hosp = "Yes" if card.get("in_hospital") else "No (waiting / untreated)"
        embed.add_field(
            name="🩹 Injury Status",
            value=(
                f"**{TIER_NAMES.get(tier, 'Injured')}** · "
                f"~**{days}** day(s) remaining · In hospital: **{hosp}**"
            ),
            inline=False,
        )
    embed.add_field(name="📈 Level & Experience Progression", value=xp_bar, inline=False)
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
        inline=False,
    )
    embed.add_field(name="✨ PlayStyles", value=playstyles_str, inline=True)
    embed.add_field(name="📄 Contract Status", value=contract_val, inline=False)
    sp_avail = int(card.get("skill_points", 0) or 0)
    overall = int(card.get("overall", 0) or 0)
    potential = int(card.get("potential", 0) or 0)
    if overall >= potential:
        mp = sp_to_mentor_units(sp_avail)
        sp_value = (
            f"**{sp_avail}** · 🎓 Mentor Ready\n"
            f"Converts to: **{mp} MP** ({mp * 500} XP)"
        )
    else:
        sp_value = f"**{sp_avail}**"
    embed.add_field(name="⭐ Skill Points Available", value=sp_value, inline=False)

    if has_evo:
        track = EVOLUTION_TRACKS.get(evo["evolution_id"], {"name": "Unknown Evolution"})
        played = _evo_played(evo)
        required = _evo_required(evo)
        progress_str = (
            f"### 🧬 {track['name']}\n"
            f"{make_match_progress_bar(played, required)}\n"
            f"*Play matches with this player in your starting XI to progress.*"
        )
        embed.add_field(name="Evolution In Progress", value=progress_str, inline=False)

    view = PlayerProfileView(player_id, owner_id, card["name"], has_evo, can_claim, renewal_cost, card, renew_allowed)
    return embed, view


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
            payload = await build_player_profile(db, player_id, interaction.user.id)
            if not payload:
                await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
                return

            embed, view = payload
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to load player profile.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlayerCog(bot))
