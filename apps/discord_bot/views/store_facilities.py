# apps/discord_bot/views/store_facilities.py
"""Club Facilities sub-hub under /store (YA + Training Ground). Hospital is on /profile."""
from __future__ import annotations

from datetime import datetime, timezone

import discord

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.embeds.hospital_embeds import hospital_panel_embed
from apps.discord_bot.core.view_helpers import disable_view_on_timeout, set_view_controls_disabled
from economy import (
    FACILITY_MAX_LEVEL,
    HOSPITAL_MAX_LEVEL,
    facility_label,
    facility_upgrade_cost,
    hospital_bed_capacity,
    hospital_recovery_multiplier,
    hospital_upgrade_cost,
    min_matches_for_next_level,
    training_ground_drill_xp_bonus,
    youth_academy_tier,
)


def _level_for(player: dict, facility_key: str) -> int:
    if facility_key == "youth_academy":
        return int(player.get("youth_academy_level", 1))
    if facility_key == "training_ground":
        return int(player.get("training_ground_level", 1))
    return int(player.get("hospital_level", 0))


def _cost_for(facility_key: str, level: int) -> int | None:
    if facility_key == "hospital":
        return hospital_upgrade_cost(level)
    return facility_upgrade_cost(level)


def _max_level(facility_key: str) -> int:
    return HOSPITAL_MAX_LEVEL if facility_key == "hospital" else FACILITY_MAX_LEVEL


def _upgrade_blocked_reason(player: dict, facility_key: str) -> str | None:
    level = _level_for(player, facility_key)
    if level >= _max_level(facility_key):
        return "Max level reached."
    cost = _cost_for(facility_key, level)
    if cost is None:
        return "Cannot upgrade."
    if int(player.get("coins", 0)) < cost:
        return f"Need 🪙 {cost:,} coins."
    next_level = level + 1
    need_matches = min_matches_for_next_level(level, facility_key)
    if need_matches and int(player.get("matches_played", 0)) < need_matches:
        return f"Requires {need_matches} career matches for L{next_level}."
    last_up = player.get("facility_last_upgrade_at")
    if last_up:
        try:
            ts = datetime.fromisoformat(str(last_up).replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - ts).days < 7:
                return "Weekly upgrade cooldown (1 per UTC week)."
        except ValueError:
            pass
    return None


def _next_upgrade_line(player: dict, facility_key: str) -> str:
    level = _level_for(player, facility_key)
    if level >= _max_level(facility_key):
        return "✅ **Max level**"
    cost = _cost_for(facility_key, level)
    need = min_matches_for_next_level(level, facility_key)
    line = f"Next: **L{level + 1}** — 🪙 **{cost:,}** coins"
    if need:
        line += f" · **{need}+** career matches"
    block = _upgrade_blocked_reason(player, facility_key)
    if block:
        line += f"\n⚠️ {block}"
    return line


def _youth_next_preview(level: int) -> str:
    if level >= FACILITY_MAX_LEVEL:
        return ""
    nxt = youth_academy_tier(level + 1)
    return (
        f"After upgrade: OVR **{nxt.ovr_min}–{nxt.ovr_max}** · POT cap **{nxt.pot_max}** · "
        f"Gem **{int(nxt.gem_chance * 100)}%**\n"
    )


def _training_next_preview(level: int) -> str:
    if level >= FACILITY_MAX_LEVEL:
        return ""
    bonus = training_ground_drill_xp_bonus(level + 1)
    return f"After upgrade: **+{bonus}** bonus drill XP per drill\n"


def facilities_embed(player: dict) -> discord.Embed:
    youth_lv = int(player.get("youth_academy_level", 1))
    tg_lv = int(player.get("training_ground_level", 1))
    youth_tier = youth_academy_tier(youth_lv)
    tg_bonus = training_ground_drill_xp_bonus(tg_lv)

    embed = discord.Embed(
        title="🏗️ Club Facilities",
        description=(
            "Optional long-term coin investments.\n"
            f"🪙 **Balance**: `{int(player.get('coins', 0)):,}` coins\n"
            "Max **1 upgrade per UTC week** across YA and Training Ground "
            "(Hospital upgrades are on `/profile` → Manage Hospital)"
        ),
        color=0x00FF87,
    )
    embed.add_field(
        name=f"🌱 Youth Academy — Level {youth_lv}/{FACILITY_MAX_LEVEL}",
        value=(
            "Improves your **weekly youth intake** (Monday UTC prospects join your roster). "
            "Does **not** affect daily gacha packs.\n"
            f"**Now:** OVR **{youth_tier.ovr_min}–{youth_tier.ovr_max}** · POT cap **{youth_tier.pot_max}** · "
            f"Gem chance **{int(youth_tier.gem_chance * 100)}%**\n"
            + _youth_next_preview(youth_lv)
            + _next_upgrade_line(player, "youth_academy")
        ),
        inline=False,
    )
    embed.add_field(
        name=f"🏋️ Training Ground — Level {tg_lv}/{FACILITY_MAX_LEVEL}",
        value=(
            "Adds flat **bonus XP** to every stat drill in `/development` "
            "(L1 = baseline, no bonus).\n"
            f"**Now:** **+{tg_bonus}** bonus drill XP per drill\n"
            + _training_next_preview(tg_lv)
            + _next_upgrade_line(player, "training_ground")
        ),
        inline=False,
    )
    embed.set_footer(text="OVR = current rating · POT = growth ceiling · Hospital: /profile")
    return embed


class FacilitiesHubView(discord.ui.View):
    def __init__(self, owner_id: int, player: dict) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.player = player

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⬆️ Upgrade Youth Academy", row=0)
    async def upgrade_youth(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self._upgrade(interaction, "youth_academy")

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⬆️ Upgrade Training Ground", row=0)
    async def upgrade_training(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self._upgrade(interaction, "training_ground")

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Store", row=1)
    async def back(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        from apps.discord_bot.cogs.store_cog import show_store
        await show_store(interaction, self.owner_id)

    async def _upgrade(self, interaction: discord.Interaction, facility_key: str) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        level = _level_for(self.player, facility_key)
        cost = _cost_for(facility_key, level)
        block = _upgrade_blocked_reason(self.player, facility_key)
        if block:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(block), ephemeral=True)
            return
        try:
            db = await get_client()
            res = await db.rpc("upgrade_club_facility", {
                "p_owner_id": self.owner_id,
                "p_facility_key": facility_key,
                "p_expected_cost": cost,
            }).execute()
            data = res.data or {}
            label = facility_label(facility_key)
            await interaction.followup.send(
                embed=success_embed(
                    f"**{label}** upgraded to **Level {data.get('new_level', level + 1)}** "
                    f"for **🪙 {data.get('coins_spent', cost):,}** coins."
                ),
                ephemeral=True,
            )
            player_res = await db.table("players").select("*").eq("discord_id", self.owner_id).maybe_single().execute()
            self.player = player_res.data or self.player
            embed = facilities_embed(self.player)
            view = FacilitiesHubView(self.owner_id, self.player)
            if interaction.message:
                await interaction.message.edit(embed=embed, view=view)
        except Exception as exc:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


class HospitalPanelView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        player: dict,
        patients: list[dict],
        waiting: list[dict],
        *,
        origin: str = "facilities",
    ) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.player = player
        self.patients = patients
        self.waiting = waiting
        self.origin = origin if origin in ("facilities", "profile") else "profile"
        if patients:
            opts = [
                discord.SelectOption(
                    label=(p.get("player_cards") or p).get("name", "Patient")[:100],
                    value=str(p.get("player_card_id") or (p.get("player_cards") or {}).get("id")),
                )
                for p in patients[:25]
            ]
            sel = discord.ui.Select(placeholder="Discharge a patient…", options=opts, row=0)
            sel.callback = self._discharge
            self.add_item(sel)
        if waiting:
            opts = [
                discord.SelectOption(label=w.get("name", "Waiting")[:100], value=str(w["id"]))
                for w in waiting[:25]
            ]
            sel = discord.ui.Select(placeholder="Admit waiting player…", options=opts, row=1)
            sel.callback = self._admit
            self.add_item(sel)

        upgrade_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="⬆️ Upgrade Hospital",
            row=2,
        )
        block = _upgrade_blocked_reason(player, "hospital")
        if block == "Max level reached.":
            upgrade_btn.disabled = True
        upgrade_btn.callback = self._upgrade_hospital
        self.add_item(upgrade_btn)

        back_label = "⬅️ Back to Profile" if self.origin == "profile" else "⬅️ Facilities"
        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label=back_label, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def _discharge(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        card_id = interaction.data["values"][0]
        try:
            db = await get_client()
            await db.rpc(
                "discharge_from_hospital",
                {"p_owner_id": self.owner_id, "p_player_card_id": card_id},
            ).execute()
            await interaction.followup.send(
                embed=success_embed("Patient discharged — they continue untreated recovery."),
                ephemeral=True,
            )
            await show_hospital_panel(interaction, self.owner_id, origin=self.origin)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    async def _admit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        card_id = interaction.data["values"][0]
        try:
            db = await get_client()
            await db.rpc(
                "admit_to_hospital",
                {"p_owner_id": self.owner_id, "p_player_card_id": card_id},
            ).execute()
            await interaction.followup.send(embed=success_embed("Player admitted to Hospital."), ephemeral=True)
            await show_hospital_panel(interaction, self.owner_id, origin=self.origin)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    async def _upgrade_hospital(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        level = _level_for(self.player, "hospital")
        cost = _cost_for("hospital", level)
        block = _upgrade_blocked_reason(self.player, "hospital")
        if block:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(block), ephemeral=True)
            return
        try:
            db = await get_client()
            res = await db.rpc("upgrade_club_facility", {
                "p_owner_id": self.owner_id,
                "p_facility_key": "hospital",
                "p_expected_cost": cost,
            }).execute()
            data = res.data or {}
            await interaction.followup.send(
                embed=success_embed(
                    f"**Hospital** upgraded to **Level {data.get('new_level', level + 1)}** "
                    f"for **🪙 {data.get('coins_spent', cost):,}** coins."
                ),
                ephemeral=True,
            )
            await show_hospital_panel(interaction, self.owner_id, origin=self.origin)
        except Exception as exc:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    async def _back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if self.origin == "profile":
            from apps.discord_bot.cogs.profile_cog import show_profile
            await show_profile(interaction, self.owner_id)
        else:
            await show_facilities(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


async def show_hospital_panel(
    interaction: discord.Interaction,
    owner_id: int,
    *,
    origin: str = "facilities",
) -> None:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data
    if not player:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return
    patients_res = await db.table("hospital_patients").select(
        "*, player_cards(id, name, position, injury_tier)"
    ).eq("owner_id", owner_id).is_("discharge_date", "null").execute()
    patients = patients_res.data or []
    waiting_res = await db.table("player_cards").select(
        "id, name, position, injury_tier, injury_recovery_days, in_hospital"
    ).eq("owner_id", owner_id).not_.is_("injury_tier", "null").eq("in_hospital", False).execute()
    waiting = waiting_res.data or []
    embed = hospital_panel_embed(player, patients=patients, waiting=waiting)
    view = HospitalPanelView(owner_id, player, patients, waiting, origin=origin)
    if interaction.response.is_done():
        if interaction.message:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


async def show_facilities(interaction: discord.Interaction, owner_id: int) -> None:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data
    if not player:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return
    embed = facilities_embed(player)
    view = FacilitiesHubView(owner_id, player)
    if interaction.response.is_done():
        if interaction.message:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)
