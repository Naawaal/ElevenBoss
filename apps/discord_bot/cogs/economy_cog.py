# apps/discord_bot/cogs/economy_cog.py
from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ext import commands

from economy.wages import calculate_xi_weekly_bill, contract_blocks_xi, contract_in_grace
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.core.economy_rpc import (
    get_game_config_int,
    get_game_config_numeric,
    wages_payroll_enabled,
)
from apps.discord_bot.core.view_helpers import disable_view_on_timeout, edit_ephemeral_hub_message


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def build_club_finances_embed(
    player: dict,
    starting_cards: list[dict],
    weekly_wages: int,
    *,
    payroll_on: bool = False,
    latest_run: dict | None = None,
    grace_days: int = 7,
    profile_pointer: bool = False,
) -> discord.Embed:
    tokens = int(player.get("tokens", 0))
    embed = discord.Embed(
        title=f"💼 Club Finances: {player['club_name']}",
        description=f"Financial statement and forecasts for Manager **{player['manager_name']}**.",
        color=0x00FF87,
    )
    embed.add_field(
        name="💰 Wallet Balances",
        value=(
            f"🪙 **Coins Balance**: `{player['coins']:,} coins`\n"
            f"💎 **Gems Balance**: `{tokens:,} gems`"
        ),
        inline=False,
    )

    wage_note = (
        "Deducted every **Monday 00:05 UTC** when payroll is enabled."
        if payroll_on
        else "*(not auto-deducted)*"
    )
    embed.add_field(
        name="👔 Starting 11 Wage Bill",
        value=(
            f"👥 **Paying players (XI)**: `{len(starting_cards)}/11`\n"
            f"📉 **Weekly wages**: `🪙 {weekly_wages:,} coins / week` {wage_note}"
        ),
        inline=False,
    )

    if payroll_on:
        debt = int(player.get("payroll_debt") or 0)
        strikes = int(player.get("payroll_strikes") or 0)
        last_at = player.get("last_payroll_at")
        last_week = player.get("last_payroll_week") or "—"
        last_paid = int((latest_run or {}).get("paid_coins") or 0) if latest_run else 0
        last_line = f"{last_week}"
        if last_at:
            ts = _parse_ts(last_at)
            if ts:
                last_line += f" · <t:{int(ts.timestamp())}:R>"
        if latest_run:
            last_line += f" · paid 🪙 {last_paid:,} ({latest_run.get('status', '?')})"

        ladder = (
            "≥2 blocks friendlies · ≥3 blocks P2P listings & youth scouting "
            "(agent sale still OK). League/bot matches stay open so you can earn coins."
        )
        embed.add_field(
            name="📉 Payroll status",
            value=(
                f"🧾 **Debt**: `🪙 {debt:,}`\n"
                f"⚠️ **Strikes**: `{strikes}`\n"
                f"🗓 **Last payroll**: {last_line}\n"
                f"⏭ **Next payroll**: Monday **00:05 UTC**\n"
                f"*{ladder}*"
            ),
            inline=False,
        )

        now = datetime.now(timezone.utc)
        in_grace = 0
        past_grace = 0
        for card in starting_cards:
            exp = _parse_ts(card.get("contract_expires_at"))
            if exp is None:
                continue
            if contract_blocks_xi(exp, now, grace_days=grace_days):
                past_grace += 1
            elif contract_in_grace(exp, now, grace_days=grace_days):
                in_grace += 1
        if in_grace or past_grace:
            embed.add_field(
                name="📝 XI contract alerts",
                value=(
                    f"⏳ In grace: **{in_grace}** · "
                    f"🚫 Past grace (cannot start): **{past_grace}**\n"
                    "Renew on `/player-profile` or replace via `/squad`."
                ),
                inline=False,
            )

    embed.add_field(
        name="🏗️ Club Facilities",
        value=(
            f"🌱 Youth Academy **L{player.get('youth_academy_level', 1)}** · "
            f"🏋️ Training Ground **L{player.get('training_ground_level', 1)}** · "
            f"🏥 Hospital **L{player.get('hospital_level', 0)}**"
        ),
        inline=False,
    )
    if profile_pointer:
        embed.set_footer(text="Unified club dashboard (finance + hospital): /profile")
    return embed


async def fetch_club_finances_embed(owner_id: int, *, profile_pointer: bool = False) -> discord.Embed | None:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data if player_res else None
    if not player:
        return None
    assignments_res = await db.table("squad_assignments").select("player_cards(*)").eq("discord_id", owner_id).execute()
    starting_cards = [a["player_cards"] for a in (assignments_res.data or []) if a.get("player_cards")]

    bill_scale = await get_game_config_numeric(db, "wages_payroll_bill_scale", 1.0)
    wage_scale = await get_game_config_numeric(db, "wage_scale_factor", 1.2)
    weekly_wages = calculate_xi_weekly_bill(
        starting_cards,
        wage_scale_factor=float(wage_scale),
        bill_scale=float(bill_scale),
    )

    payroll_on = await wages_payroll_enabled(db)
    latest_run = None
    if payroll_on:
        run_res = (
            await db.table("payroll_runs")
            .select("paid_coins, status, week_key, created_at")
            .eq("club_id", owner_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = run_res.data or []
        latest_run = rows[0] if rows else None

    grace_days = await get_game_config_int(db, "contract_grace_days", 7)
    return build_club_finances_embed(
        player,
        starting_cards,
        weekly_wages,
        payroll_on=payroll_on,
        latest_run=latest_run,
        grace_days=grace_days,
        profile_pointer=profile_pointer,
    )


class ClubFinancesPanelView(discord.ui.View):
    """Finances detail opened from /profile; Back refreshes the profile dashboard."""

    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Profile", row=0)
    async def back(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.cogs.profile_cog import show_profile
        await show_profile(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


async def show_club_finances_panel(interaction: discord.Interaction, owner_id: int) -> None:
    embed = await fetch_club_finances_embed(owner_id, profile_pointer=False)
    if embed is None:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return
    view = ClubFinancesPanelView(owner_id)
    await edit_ephemeral_hub_message(interaction, embed, view)


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))
