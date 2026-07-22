# apps/discord_bot/cogs/leaderboard_cog.py
"""Unified rankings hub — Division Rank, Global LP, Season Pts (US-30)."""
from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.core.competitive_display import profile_leaderboard_hint, resolve_global_tier
from apps.discord_bot.core.division_cache import load_global_divisions
from apps.discord_bot.core.view_helpers import (
    disable_view_on_timeout,
    edit_ephemeral_hub_message,
    set_view_controls_disabled,
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.core.scheduler_jobs import DIVISIONS
from leagues import (
    LeagueEntry,
    compute_promotions_relegations,
    format_rank_line,
    format_standings_table,
    highest_unclaimed_tier,
    iso_week_utc,
    paginate_rows,
    promotion_zone_labels,
    tier_progress_label,
    tie_breaker_footer,
    viewer_page_index,
    weekly_reset_countdown,
    zone_suffix,
)

logger = logging.getLogger(__name__)

TAB_DIVISION = "division"
TAB_GLOBAL = "global"
TAB_SEASON = "season"


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="leaderboard",
        description="View Division Rank, Global LP, and guild Season standings.",
    )
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        from apps.discord_bot.core import perf_signals

        with perf_signals.hub_timer("leaderboard"):
            db = await get_client()
            player_res = await db.table("players").select("*").eq(
                "discord_id", interaction.user.id
            ).maybe_single().execute()
            player = player_res.data if player_res else None
            if not player:
                await interaction.followup.send(embed=error_embed("Player not found."), ephemeral=True)
                return

            division = player.get("division", "Grassroots")
            page = 0
            view = LeaderboardView(
                self,
                owner_id=interaction.user.id,
                tab=TAB_DIVISION,
                division=division,
                page=page,
                guild_id=interaction.guild_id,
            )
            embed, unclaimed = await asyncio.gather(
                self.build_embed(
                    db,
                    tab=TAB_DIVISION,
                    viewer=player,
                    division=division,
                    page=page,
                    guild_id=interaction.guild_id,
                ),
                self.unclaimed_tier_for(db, player),
            )
            view.set_claim_state(unclaimed)
            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg

    async def build_embed(
        self,
        db,
        *,
        tab: str,
        viewer: dict,
        division: str,
        page: int,
        guild_id: int | None,
    ) -> discord.Embed:
        if tab == TAB_DIVISION:
            return await self._division_embed(db, viewer, division, page)
        if tab == TAB_GLOBAL:
            return await self._global_embed(db, viewer, page)
        return await self._season_embed(db, viewer, guild_id)

    async def _division_embed(self, db, viewer: dict, division: str, page: int) -> discord.Embed:
        res = await db.table("players").select(
            "discord_id, club_name, league_points, goal_difference"
        ).eq("division", division).eq("is_ai", False).order(
            "league_points", desc=True
        ).order("goal_difference", desc=True).execute()
        rows = res.data or []
        viewer_id = viewer["discord_id"]
        viewer_rank = 0
        for idx, row in enumerate(rows, 1):
            if row["discord_id"] == viewer_id:
                viewer_rank = idx
                break

        if viewer_rank and page == 0:
            page = viewer_page_index(viewer_rank)

        entries = [
            LeagueEntry(
                discord_id=r["discord_id"],
                league_points=r["league_points"],
                goal_difference=r["goal_difference"],
            )
            for r in rows
        ]
        promo_res = compute_promotions_relegations(entries) if entries else None
        n_promo = len(promo_res.promoted_ids) if promo_res else 0
        n_releg = len(promo_res.relegated_ids) if promo_res else 0

        page_rows, total_pages, page = paginate_rows(rows, page)
        lines: list[str] = []
        base_pos = page * 10
        for i, row in enumerate(page_rows):
            pos = base_pos + i + 1
            zone = zone_suffix(pos, len(rows), n_promo, n_releg)
            lines.append(
                format_rank_line(
                    pos,
                    row.get("club_name", "?"),
                    row["league_points"],
                    row["goal_difference"],
                    viewer_id,
                    row["discord_id"],
                    zone=zone,
                )
            )

        promo_rng, releg_rng = promotion_zone_labels(len(rows))
        weekly_pts = int(viewer.get("league_points", 0))
        claimed = await self._claimed_tiers(db, viewer_id)
        unclaimed = highest_unclaimed_tier(weekly_pts, claimed)

        embed = discord.Embed(
            title=f"⚔️ Division Rank — {division}",
            description=f"Resets in **{weekly_reset_countdown()}** · Top 20% promote · Bottom 20% relegate",
            color=0x00FF87,
        )
        embed.add_field(
            name="Standings",
            value="```\n" + ("\n".join(lines) if lines else "No managers in this division yet.") + "\n```",
            inline=False,
        )
        if viewer_rank:
            embed.add_field(
                name="Your standing",
                value=(
                    f"Rank **#{viewer_rank}** of **{len(rows)}** in **{division}** · "
                    f"**{weekly_pts}** pts (GD {viewer.get('goal_difference', 0):+d})\n"
                    f"Weekly tiers: {tier_progress_label(weekly_pts)}\n"
                    f"Promotion zone: {promo_rng} · Relegation zone: {releg_rng}"
                ),
                inline=False,
            )
        footer = profile_leaderboard_hint()
        if total_pages > 1:
            footer = f"Page {page + 1}/{total_pages} · {footer}"
        embed.set_footer(text=footer)
        return embed

    async def _global_embed(self, db, viewer: dict, page: int) -> discord.Embed:
        divisions, res = await asyncio.gather(
            load_global_divisions(db),
            db.table("players")
            .select("discord_id, club_name, global_lp")
            .eq("is_ai", False)
            .order("global_lp", desc=True)
            .limit(100)
            .execute(),
        )
        rows = res.data or []
        viewer_id = viewer["discord_id"]
        user_lp = int(viewer.get("global_lp", 0))
        viewer_rank = next((i + 1 for i, r in enumerate(rows) if r["discord_id"] == viewer_id), 0)
        if not viewer_rank:
            higher_res = await db.table("players").select(
                "discord_id", count="exact"
            ).eq("is_ai", False).gt("global_lp", user_lp).execute()
            viewer_rank = (higher_res.count or 0) + 1
        if viewer_rank and page == 0 and any(r["discord_id"] == viewer_id for r in rows):
            page = viewer_page_index(viewer_rank)

        page_rows, total_pages, page = paginate_rows(rows, page)
        lines: list[str] = []
        base_pos = page * 10
        for i, row in enumerate(page_rows):
            pos = base_pos + i + 1
            tier_name, _, _ = resolve_global_tier(int(row.get("global_lp", 0)), divisions)
            marker = "▶ " if row["discord_id"] == viewer_id else "  "
            name = (row.get("club_name") or "?")[:18]
            lines.append(f"{marker}#{pos}  {name:<18} {row['global_lp']:>5} LP  · {tier_name}")

        tier_name, _, next_div = resolve_global_tier(user_lp, divisions)
        progress = f"**{user_lp} LP** ({tier_name})"
        if next_div:
            progress = f"**{user_lp}/{next_div['min_lp']} LP** to {next_div['name']}"

        embed = discord.Embed(
            title="🌍 Global LP Leaderboard",
            description="Persistent rank · Never resets · Drives bot difficulty",
            color=0x00FF87,
        )
        embed.add_field(
            name="Top managers",
            value="```\n" + ("\n".join(lines) if lines else "No data yet.") + "\n```",
            inline=False,
        )
        embed.add_field(
            name="Your standing",
            value=f"Rank **#{viewer_rank}** globally · {progress}",
            inline=False,
        )
        footer = f"Page {page + 1}/{total_pages}" if total_pages > 1 else "Cross-server ranking"
        embed.set_footer(text=footer)
        return embed

    async def _season_embed(self, db, viewer: dict, guild_id: int | None) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Season Standings",
            color=0x00FF87,
        )
        if not guild_id:
            embed.description = (
                "Season standings are **guild-only**. Run `/leaderboard` inside your server."
            )
            return embed

        league_res = await db.table("leagues").select("id, name").eq(
            "guild_id", guild_id
        ).maybe_single().execute()
        if not league_res or not league_res.data:
            embed.description = "No league configured for this server. Ask an admin to set one up."
            return embed

        season_res = await db.table("league_seasons").select("id, status, current_matchday").eq(
            "league_id", league_res.data["id"]
        ).eq("status", "active").maybe_single().execute()
        if not season_res or not season_res.data:
            embed.description = (
                "No **active** guild season. Check `/league hub` for registration or the next season."
            )
            return embed

        from apps.discord_bot.cogs.league_cog import fetch_standings

        season = season_res.data
        standings, fixtures_res, part_res = await asyncio.gather(
            fetch_standings(db, season["id"]),
            db.table("league_fixtures").select("*").eq("season_id", season["id"]).execute(),
            db.table("league_participants")
            .select("player_id")
            .eq("season_id", season["id"])
            .eq("player_id", viewer["discord_id"])
            .maybe_single()
            .execute(),
        )
        fixtures = fixtures_res.data or []
        table = format_standings_table(standings, fixtures, limit=15)

        registered = bool(part_res and part_res.data)

        embed.title = f"🏆 Season Standings — {league_res.data['name']}"
        embed.description = (
            f"Matchday **{season.get('current_matchday', '?')}** · "
            "**Season Pts** from league fixtures only (not Division Rank)."
        )
        embed.add_field(name="Table", value=f"```\n{table}\n```\n{tie_breaker_footer()}", inline=False)
        if not registered:
            embed.add_field(
                name="Note",
                value="You're not registered this season. Spectating only — use `/league hub` to join.",
                inline=False,
            )
        embed.set_footer(text="Full league hub: /league hub")
        return embed

    async def _claimed_tiers(self, db, player_id: int) -> set[str] | None:
        iso_week = iso_week_utc()
        try:
            res = await db.table("weekly_rank_rewards").select("tier").eq(
                "player_id", player_id
            ).eq("iso_week", iso_week).execute()
            return {r["tier"] for r in (res.data or [])}
        except Exception:
            logger.warning("weekly_rank_rewards read failed", exc_info=True)
            return None

    async def unclaimed_tier_for(self, db, viewer: dict) -> str | None:
        claimed = await self._claimed_tiers(db, viewer["discord_id"])
        if claimed is None:
            return None
        return highest_unclaimed_tier(int(viewer.get("league_points", 0)), claimed)

    async def claim_weekly_tier(self, interaction: discord.Interaction, tier: str) -> bool:
        try:
            db = await get_client()
            res = await db.rpc(
                "claim_weekly_rank_tier",
                {"p_player_id": interaction.user.id, "p_tier": tier},
            ).execute()
        except Exception as exc:
            logger.exception("claim_weekly_rank_tier failed")
            await interaction.followup.send(
                embed=error_embed(f"Could not claim **{tier}** tier: {exc}"),
                ephemeral=True,
            )
            return False
        data = res.data or {}
        if not data.get("ok"):
            reason = data.get("reason", "unknown")
            msg = {
                "already_claimed": f"You already claimed the **{tier.title()}** weekly reward.",
                "threshold_not_met": "You haven't earned enough Division Rank pts for this tier yet.",
            }.get(reason, f"Could not claim **{tier}** tier ({reason}).")
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
            return False
        coins = data.get("coins", 0)
        await interaction.followup.send(
            f"🎁 Claimed **{tier.title()} Weekly** reward: **+{coins:,}** coins!",
            ephemeral=True,
        )
        return True


class LeaderboardView(discord.ui.View):
    def __init__(
        self,
        cog: LeaderboardCog,
        *,
        owner_id: int,
        tab: str,
        division: str,
        page: int,
        guild_id: int | None,
    ) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.owner_id = owner_id
        self.tab = tab
        self.division = division
        self.page = page
        self.guild_id = guild_id
        self.message: discord.Message | None = None
        self._sync_tab_styles()
        self._sync_pagination()
        if self.tab == TAB_DIVISION:
            self._add_division_select()

    def set_claim_state(self, tier: str | None) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "lb_claim":
                child.disabled = self.tab != TAB_DIVISION or not tier
                if tier:
                    child.label = f"🎁 Claim {tier.title()} Weekly"

    def _sync_tab_styles(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "lb_tab_division":
                child.style = discord.ButtonStyle.primary if self.tab == TAB_DIVISION else discord.ButtonStyle.secondary
            elif child.custom_id == "lb_tab_global":
                child.style = discord.ButtonStyle.primary if self.tab == TAB_GLOBAL else discord.ButtonStyle.secondary
            elif child.custom_id == "lb_tab_season":
                child.style = discord.ButtonStyle.primary if self.tab == TAB_SEASON else discord.ButtonStyle.secondary

    def _sync_pagination(self) -> None:
        show_div = self.tab == TAB_DIVISION
        show_page = self.tab in (TAB_DIVISION, TAB_GLOBAL)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "lb_prev":
                    child.disabled = self.page <= 0
                    child.row = 2
                    child.style = discord.ButtonStyle.secondary
                    if not show_page:
                        child.disabled = True
                elif child.custom_id == "lb_next":
                    child.row = 2
                    if not show_page:
                        child.disabled = True
                elif child.custom_id == "lb_claim":
                    child.row = 2
                    child.disabled = not show_div
                elif child.custom_id == "lb_refresh":
                    child.row = 3

    def _add_division_select(self) -> None:
        options = [
            discord.SelectOption(label=d, value=d, default=(d == self.division))
            for d in DIVISIONS
        ]
        select = discord.ui.Select(
            placeholder="Filter division…",
            options=options,
            row=1,
            custom_id="lb_division_select",
        )
        select.callback = self._division_select_callback
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This menu belongs to another manager.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)
        if self.message and self.message.embeds:
            try:
                embed = self.message.embeds[0]
                embed.set_footer(text="Session timed out. Run /leaderboard to restart.")
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

    async def _switch_tab(self, interaction: discord.Interaction, tab: str) -> None:
        await interaction.response.defer(ephemeral=True)
        self.tab = tab
        self.page = 0
        db = await get_client()
        player_res = await db.table("players").select("*").eq(
            "discord_id", self.owner_id
        ).maybe_single().execute()
        viewer = player_res.data if player_res else {}
        new_view = LeaderboardView(
            self.cog,
            owner_id=self.owner_id,
            tab=tab,
            division=self.division,
            page=0,
            guild_id=self.guild_id,
        )
        embed = await self.cog.build_embed(
            db,
            tab=tab,
            viewer=viewer,
            division=self.division,
            page=0,
            guild_id=self.guild_id,
        )
        unclaimed = await self.cog.unclaimed_tier_for(db, viewer)
        new_view.set_claim_state(unclaimed)
        new_view.message = self.message
        await edit_ephemeral_hub_message(interaction, embed, new_view)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        db = await get_client()
        player_res = await db.table("players").select("*").eq(
            "discord_id", self.owner_id
        ).maybe_single().execute()
        viewer = player_res.data if player_res else {}
        embed = await self.cog.build_embed(
            db,
            tab=self.tab,
            viewer=viewer,
            division=self.division,
            page=self.page,
            guild_id=self.guild_id,
        )
        unclaimed = await self.cog.unclaimed_tier_for(db, viewer)
        set_view_controls_disabled(self, disabled=False)
        self.set_claim_state(unclaimed)
        await edit_ephemeral_hub_message(interaction, embed, self)

    async def _division_select_callback(self, interaction: discord.Interaction) -> None:
        select = interaction.data.get("values", [])
        if select:
            self.division = select[0]
            self.page = 0
        await self._refresh(interaction)

    @discord.ui.button(label="⚔️ Division Rank", custom_id="lb_tab_division", row=0)
    async def tab_division(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._switch_tab(interaction, TAB_DIVISION)

    @discord.ui.button(label="🌍 Global LP", custom_id="lb_tab_global", row=0)
    async def tab_global(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._switch_tab(interaction, TAB_GLOBAL)

    @discord.ui.button(label="🏆 Season", custom_id="lb_tab_season", row=0)
    async def tab_season(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._switch_tab(interaction, TAB_SEASON)

    @discord.ui.button(label="◀ Prev", custom_id="lb_prev", row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", custom_id="lb_next", row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page += 1
        await self._refresh(interaction)

    @discord.ui.button(label="🎁 Claim Weekly", custom_id="lb_claim", row=2, style=discord.ButtonStyle.success)
    async def claim_weekly(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            player_res = await db.table("players").select("*").eq(
                "discord_id", self.owner_id
            ).maybe_single().execute()
            viewer = player_res.data or {}
            tier = await self.cog.unclaimed_tier_for(db, viewer)
            if not tier:
                await interaction.followup.send("No weekly tier available to claim.", ephemeral=True)
                set_view_controls_disabled(self, disabled=False)
                return
            if await self.cog.claim_weekly_tier(interaction, tier):
                await self._refresh(interaction)
            else:
                set_view_controls_disabled(self, disabled=False)
        except Exception as exc:
            logger.exception("Leaderboard weekly claim failed")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    @discord.ui.button(label="🔄 Refresh", custom_id="lb_refresh", row=3, style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._refresh(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
