# apps/discord_bot/views/academy_hub.py
"""Manage Academy hub under /profile (015)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord

from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.core.card_payload import card_rpc_payload
from apps.discord_bot.core.economy_rpc import wages_market_block_message
from apps.discord_bot.core.view_helpers import (
    add_select_if_options,
    disable_view_on_timeout,
    set_view_controls_disabled,
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.academy_embeds import academy_hub_embed, scout_shortlist_embed
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from economy import academy_slot_cap, scout_tier_cost, scout_tier_hours
from gacha import generate_youth_intake
from player_engine import READY_OVR_DEFAULT, is_promotion_ready

logger = logging.getLogger(__name__)


async def _load_academy_state(owner_id: int) -> tuple[dict, list[dict], dict | None, int, int]:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data or {}
    level = int(player.get("youth_academy_level", 1))
    cap = academy_slot_cap(level)
    cards_res = (
        await db.table("player_cards")
        .select("*")
        .eq("owner_id", owner_id)
        .eq("in_academy", True)
        .eq("is_retired", False)
        .order("overall", desc=True)
        .execute()
    )
    prospects = cards_res.data or []
    report_res = (
        await db.table("scouting_reports")
        .select("*")
        .eq("owner_id", owner_id)
        .is_("signed_card_id", "null")
        .gt("expires_at", datetime.now(timezone.utc).isoformat())
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    reports = report_res.data or []
    report = reports[0] if reports else None
    return player, prospects, report, len(prospects), cap


async def show_academy_hub(
    interaction: discord.Interaction,
    owner_id: int,
    *,
    origin: str = "profile",
) -> None:
    player, prospects, report, used, cap = await _load_academy_state(owner_id)
    if not player:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return
    embed = academy_hub_embed(player, prospects, slots_used=used, slots_cap=cap, report=report)
    view = AcademyHubView(owner_id, player, prospects, report, origin=origin)
    if interaction.response.is_done():
        if interaction.message:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class AcademyHubView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        player: dict,
        prospects: list[dict],
        report: dict | None,
        *,
        origin: str = "profile",
    ) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.player = player
        self.prospects = prospects
        self.report = report
        self.origin = origin
        self.selected_id: str | None = str(prospects[0]["id"]) if len(prospects) == 1 else None

        if prospects:
            opts = [
                discord.SelectOption(
                    label=f"{p.get('position', '?')} {p.get('name', '?')}"[:100],
                    description=f"{p.get('overall', '?')} OVR · age {p.get('age', '?')}"[:100],
                    value=str(p["id"]),
                )
                for p in prospects[:25]
            ]
            add_select_if_options(
                self,
                placeholder="Select an academy prospect…",
                options=opts,
                row=0,
                callback=self._on_select,
            )

        promote_btn = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="⬆️ Promote",
            row=1,
            disabled=not self.selected_id,
            custom_id=f"academy_promote_{owner_id}",
        )
        promote_btn.callback = self._promote
        self.promote_btn = promote_btn
        self.add_item(promote_btn)

        release_btn = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="🗑️ Release",
            row=1,
            disabled=not self.selected_id,
            custom_id=f"academy_release_{owner_id}",
        )
        release_btn.callback = self._release
        self.release_btn = release_btn
        self.add_item(release_btn)

        for i, (tier, label) in enumerate(
            (("quick", "Quick"), ("standard", "Standard"), ("deep", "Deep"))
        ):
            cost = scout_tier_cost(tier) or 0
            hours = scout_tier_hours(tier) or 0
            btn = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label=f"🔍 {label} ({cost // 1000}k · {hours}h)",
                row=2,
                custom_id=f"academy_scout_{tier}",
            )
            btn.callback = self._make_scout_callback(tier)
            self.add_item(btn)

        if report:
            claim_btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="📋 Open Scout Report",
                row=3,
            )
            claim_btn.callback = self._open_report
            self.add_item(claim_btn)

        refresh_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="🔄 Refresh", row=3)
        refresh_btn.callback = self._refresh
        self.add_item(refresh_btn)

        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Profile", row=3)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        self.selected_id = interaction.data["values"][0]
        self.promote_btn.disabled = False
        self.release_btn.disabled = False
        card = next((p for p in self.prospects if str(p["id"]) == self.selected_id), None)
        note = ""
        if card and not is_promotion_ready(int(card.get("overall", 0))):
            note = f" (below Ready {READY_OVR_DEFAULT} — early promote OK)"
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            logger.exception("Academy select failed to refresh view for owner %s", self.owner_id)
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                f"Selected **{(card or {}).get('name', 'prospect')}**{note}.",
                ephemeral=True,
            )
            if interaction.message:
                await interaction.message.edit(view=self)
            return
        await interaction.followup.send(
            f"Selected **{(card or {}).get('name', 'prospect')}**{note}.",
            ephemeral=True,
        )

    async def _promote(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not self.selected_id:
            await interaction.followup.send(embed=error_embed("Select a prospect first."), ephemeral=True)
            return
        card = next((p for p in self.prospects if str(p["id"]) == self.selected_id), None)
        early = card and not is_promotion_ready(int(card.get("overall", 0)))
        try:
            db = await get_client()
            res = await db.rpc(
                "promote_academy_player",
                {"p_owner_id": self.owner_id, "p_card_id": self.selected_id},
            ).execute()
            data = res.data or {}
            early_flag = data.get("early_promote", early)
            msg = f"**{(card or {}).get('name', 'Player')}** promoted to the senior club."
            if early_flag:
                msg += " _(Early promote — they would have kept growing in the academy.)_"
            await interaction.followup.send(embed=success_embed(msg), ephemeral=True)
            await show_academy_hub(interaction, self.owner_id, origin=self.origin)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)

    async def _release(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not self.selected_id:
            await interaction.followup.send(embed=error_embed("Select a prospect first."), ephemeral=True)
            return
        card = next((p for p in self.prospects if str(p["id"]) == self.selected_id), None)
        name = (card or {}).get("name", "Prospect")
        view = ReleaseConfirmView(self.owner_id, self.selected_id, name, origin=self.origin)
        await interaction.followup.send(
            embed=discord.Embed(
                title="Confirm release",
                description=(
                    f"Release **{name}** from the academy?\n"
                    "They leave your club permanently (slot frees)."
                ),
                color=0xE74C3C,
            ),
            view=view,
            ephemeral=True,
        )

    def _make_scout_callback(self, tier: str):
        async def _cb(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            set_view_controls_disabled(self, disabled=True)
            try:
                db = await get_client()
                wage_msg = await wages_market_block_message(db, self.owner_id)
                if wage_msg:
                    set_view_controls_disabled(self, disabled=False)
                    await interaction.followup.send(embed=error_embed(wage_msg), ephemeral=True)
                    return
                # Auto-finalize if timer elapsed
                finishes = self.player.get("scouting_finishes_at")
                if finishes:
                    try:
                        ts = datetime.fromisoformat(str(finishes).replace("Z", "+00:00"))
                        if ts <= datetime.now(timezone.utc):
                            await _finalize_if_due(self.owner_id, self.player)
                    except ValueError:
                        pass
                res = await db.rpc(
                    "dispatch_youth_scout",
                    {"p_owner_id": self.owner_id, "p_tier": tier},
                ).execute()
                data = res.data or {}
                await interaction.followup.send(
                    embed=success_embed(
                        f"Scout **{tier}** started for 🪙 **{data.get('cost', 0):,}**. "
                        f"Finishes `<t:{int(datetime.fromisoformat(str(data['finishes_at']).replace('Z', '+00:00')).timestamp())}:R>`."
                    ),
                    ephemeral=True,
                )
                await show_academy_hub(interaction, self.owner_id, origin=self.origin)
            except Exception as exc:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)

        return _cb

    async def _open_report(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await _finalize_if_due(self.owner_id, self.player)
            player, prospects, report, used, cap = await _load_academy_state(self.owner_id)
            self.player, self.prospects, self.report = player, prospects, report
            if not report:
                await interaction.followup.send(
                    embed=error_embed("No claimable scout report. Dispatch a scout or wait for it to finish."),
                    ephemeral=True,
                )
                await show_academy_hub(interaction, self.owner_id, origin=self.origin)
                return
            prospects_json = report.get("prospects_json") or []
            embed = scout_shortlist_embed(
                str(report.get("tier", "standard")),
                prospects_json if isinstance(prospects_json, list) else [],
                report_id=str(report["id"]),
            )
            view = ScoutSignView(
                self.owner_id, str(report["id"]), prospects_json, origin=self.origin
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await _finalize_if_due(self.owner_id, self.player)
        except Exception:
            logger.exception("Academy refresh finalize failed for %s", self.owner_id)
        await show_academy_hub(interaction, self.owner_id, origin=self.origin)

    async def _back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.cogs.profile_cog import show_profile

        await show_profile(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


class ReleaseConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, card_id: str, name: str, *, origin: str = "profile") -> None:
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.card_id = card_id
        self.name = name
        self.origin = origin

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.danger, label="Confirm release")
    async def confirm(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            await db.rpc(
                "release_academy_player",
                {"p_owner_id": self.owner_id, "p_card_id": self.card_id},
            ).execute()
            await interaction.followup.send(
                embed=success_embed(f"**{self.name}** released — gone from your club. Slot freed."),
                ephemeral=True,
            )
            await show_academy_hub(interaction, self.owner_id, origin=self.origin)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="Cancel")
    async def cancel(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Release cancelled.", ephemeral=True)


class ScoutSignView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        report_id: str,
        prospects: list,
        *,
        origin: str = "profile",
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.report_id = report_id
        self.origin = origin
        opts = []
        for i, p in enumerate((prospects or [])[:3]):
            if not isinstance(p, dict):
                continue
            opts.append(
                discord.SelectOption(
                    label=f"{p.get('position', '?')} {p.get('name', i)}"[:100],
                    value=str(i),
                    description=f"Sign index {i}"[:100],
                )
            )
        if opts:
            add_select_if_options(
                self,
                placeholder="Sign one prospect…",
                options=opts,
                row=0,
                callback=self._sign,
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def _sign(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        idx = int(interaction.data["values"][0])
        try:
            db = await get_client()
            wage_msg = await wages_market_block_message(db, self.owner_id)
            if wage_msg:
                await interaction.followup.send(embed=error_embed(wage_msg), ephemeral=True)
                return
            res = await db.rpc(
                "sign_youth_scout_prospect",
                {
                    "p_owner_id": self.owner_id,
                    "p_report_id": self.report_id,
                    "p_index": idx,
                },
            ).execute()
            data = res.data or {}
            await interaction.followup.send(
                embed=success_embed(f"Signed into academy (`{data.get('card_id', '')}`)."),
                ephemeral=True,
            )
            await show_academy_hub(interaction, self.owner_id, origin=self.origin)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)


async def _finalize_if_due(owner_id: int, player: dict) -> dict | None:
    finishes = player.get("scouting_finishes_at")
    if not finishes:
        return None
    try:
        ts = datetime.fromisoformat(str(finishes).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts > datetime.now(timezone.utc):
        return None
    level = int(player.get("youth_academy_level", 1))
    cards = generate_youth_intake(academy_level=level)
    payload = [card_rpc_payload(c) for c in cards[:3]]
    while len(payload) < 3:
        payload.append(payload[-1] if payload else {})
    db = await get_client()
    tier = player.get("scouting_active_tier") or "standard"
    res = await db.rpc(
        "finalize_youth_scout_report",
        {"p_owner_id": owner_id, "p_prospects": payload[:3], "p_tier": tier},
    ).execute()
    return res.data
