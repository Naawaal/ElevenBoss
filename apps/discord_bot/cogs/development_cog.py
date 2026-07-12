# apps/discord_bot/cogs/development_cog.py
from __future__ import annotations
import logging
import os
from datetime import date, datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.core.card_payload import effective_card_age
from apps.discord_bot.core.drill_rpc import parse_stat_drill_result
from apps.discord_bot.core.select_helpers import rebuild_select_options
from apps.discord_bot.core.view_helpers import (
    disable_view_on_timeout,
    edit_ephemeral_hub_message,
    safe_defer,
    set_view_controls_disabled,
)
from player_engine import (
    CANCEL_FEE_COINS,
    EVOLUTION_START_ENERGY,
    EVOLUTION_TRACKS,
    L_MAX,
    MAX_ACTIVE_EVOLUTIONS,
    DRILL_CATALOG,
    calculate_true_ovr,
    drill_spec,
    drill_unlocked,
    drill_xp_reward,
    effective_daily_drill_count,
    evolution_start_cost,
    evolution_unlocked,
    format_cooldown_remaining,
    fusion_xp_reward,
    is_mentor_target,
    level_from_xp,
    mentor_max_units,
    passive_recovery_amount,
    preview_mentor_transfer,
    simulate_apply_card_xp,
    sp_to_mentor_units,
    stats_from_card,
    track_min_player_level,
    xp_progress,
)

from apps.discord_bot.middleware.match_lock import assert_not_in_match
from apps.discord_bot.views.level_reward_claim import claim_level_rewards, unclaimed_reward_count
from apps.discord_bot.core.economy_rpc import format_action_energy_status_async, sync_action_energy, get_game_config_int
from economy.flows import drill_cost, EconomyConfig

logger = logging.getLogger(__name__)


def _mentor_enabled() -> bool:
    raw = os.environ.get("MENTOR_TRANSFUSION_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _api_message(exc: Exception) -> str:
    return api_error_message(exc)


def _evo_played(evo: dict) -> int:
    if evo.get("matches_played") is not None:
        return int(evo["matches_played"])
    return int(evo.get("current_progress", 0))


def _evo_required(evo: dict) -> int:
    if evo.get("matches_required") is not None:
        return int(evo["matches_required"])
    return int(evo.get("target_goal", 3))


def make_match_progress_bar(played: int, required: int) -> str:
    total_bars = 10
    if required <= 0:
        return "`[░░░░░░░░░░]`"
    filled = min(total_bars, int((played / required) * total_bars))
    empty = total_bars - filled
    pct = int((played / required) * 100) if required else 0
    return f"`[{'█' * filled}{'░' * empty}]` **{played}/{required}** ({pct}%)"


def _is_active_evo(evo: dict | None) -> bool:
    return bool(evo and evo.get("status", "active") == "active")


async def fetch_evolution_hub_status(db, owner_id: int) -> dict:
    res = await db.rpc("get_evolution_hub_status", {"p_owner_id": owner_id}).execute()
    return res.data or {}


def evolution_start_gate_message(status: dict) -> str | None:
    active_count = int(status.get("active_count", 0))
    if active_count > MAX_ACTIVE_EVOLUTIONS:
        return (
            f"You have **{active_count}** active evolutions but the club limit is **{MAX_ACTIVE_EVOLUTIONS}**. "
            "Cancel excess tracks from the Evolution hub to start new ones."
        )
    if active_count >= MAX_ACTIVE_EVOLUTIONS:
        return (
            f"You already have {MAX_ACTIVE_EVOLUTIONS} evolutions in progress. "
            "Wait for one to complete or cancel an existing one."
        )
    if status.get("can_start"):
        return None
    remaining = int(status.get("cooldown_remaining_seconds", 0))
    if remaining > 0:
        return f"Next evolution available in {format_cooldown_remaining(remaining)}."
    return "You cannot start a new evolution right now."


STAT_DRILLS = {
    drill_id: meta["name"]
    for drill_id, meta in DRILL_CATALOG.items()
}


# --- Navigation / Switch helpers ---
async def show_hub(interaction: discord.Interaction, owner_id: int):
    if not await safe_defer(interaction, ephemeral=True):
        return
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data if player_res else None

    energy_row = await sync_action_energy(db, owner_id)
    ae = energy_row.get("action_energy", 0)
    max_e = energy_row.get("max_energy", 120)

    pending_count = await unclaimed_reward_count(owner_id)

    embed = discord.Embed(
        title="🏋️‍♂️ Development Center",
        description=(
            f"Welcome to **{player['club_name']}** development center. "
            f"Train stats, fuse cards, evolve playstyles, or allocate skill points.\n\n"
            f"{await format_action_energy_status_async(db, ae, max_e)}"
        ),
        color=0x00FF87,
    )
    if pending_count > 0:
        embed.add_field(
            name="🎁 Level-Up Rewards",
            value=(
                f"You have **{pending_count}** player(s) with unclaimed retroactive skill points. "
                "Use **Claim Level Rewards** below (also sent via DM when possible)."
            ),
            inline=False,
        )
    view = DevelopmentHubView(owner_id, show_claim_rewards=pending_count > 0)
    await edit_ephemeral_hub_message(interaction, embed, view)

# --- VIEWS ---

class DevelopmentHubView(discord.ui.View):
    def __init__(self, owner_id: int, *, show_claim_rewards: bool = False) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        if show_claim_rewards:
            claim_btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="🎁 Claim Level Rewards",
                custom_id="hub_claim_level_rewards",
                row=2,
            )
            claim_btn.callback = self._claim_rewards_btn
            self.add_item(claim_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def _claim_rewards_btn(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            if await unclaimed_reward_count(self.owner_id) <= 0:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(
                    embed=error_embed("No unclaimed level rewards found."),
                    ephemeral=True,
                )
                return
            claimed, total = await claim_level_rewards(self.owner_id)
            if claimed <= 0:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(
                    embed=error_embed("No rewards could be claimed."),
                    ephemeral=True,
                )
                return
            await interaction.followup.send(
                embed=success_embed(
                    f"Claimed **{total}** skill points for **{claimed}** player(s). "
                    "Use **Allocate Skills** below to spend them."
                ),
                ephemeral=True,
            )
            await show_hub(interaction, self.owner_id)
        except Exception as exc:
            logger.exception("Failed claiming level rewards from development hub.")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🏋️ Training Drills", custom_id="hub_drills", row=0)
    async def training_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await show_training_menu(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🧬 Evolutions", custom_id="hub_evos", row=0)
    async def evolutions_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await show_club_evolutions_hub(interaction, self.owner_id)

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
    if not await safe_defer(interaction, ephemeral=True):
        return
    db = await get_client()
    player_res = await db.table("players").select(
        "daily_drill_count, daily_drill_reset_at, training_ground_level"
    ).eq("discord_id", owner_id).maybe_single().execute()
    energy_row = await sync_action_energy(db, owner_id)
    training_energy = energy_row.get("action_energy", energy_row.get("training_energy", 0))
    max_e = int(energy_row.get("max_energy", 120) or 120)
    regen_per_min = float(energy_row.get("regen_per_min") or (1 / 6))
    raw_count = int((player_res.data or {}).get("daily_drill_count", 0) or 0) if player_res else 0
    reset_raw = (player_res.data or {}).get("daily_drill_reset_at") if player_res else None
    reset_at = None
    if reset_raw:
        if isinstance(reset_raw, str):
            reset_at = date.fromisoformat(reset_raw[:10])
        elif hasattr(reset_raw, "year"):
            reset_at = reset_raw if isinstance(reset_raw, date) else reset_raw.date()
    today_utc = datetime.now(timezone.utc).date()
    daily_count = effective_daily_drill_count(raw_count, reset_at, today=today_utc)
    tg_level = int((player_res.data or {}).get("training_ground_level", 1)) if player_res else 1
    daily_limit = 20
    daily_passive = passive_recovery_amount(tg_level)

    # Config-driven drill tier values (mirror process_stat_drill).
    adv_min_level = await get_game_config_int(db, "drill_advanced_min_level", 10)
    basic_energy_cfg = await get_game_config_int(db, "drill_basic_energy", 10)
    adv_energy_cfg = await get_game_config_int(db, "drill_advanced_energy", 15)
    basic_xp_cfg = await get_game_config_int(db, "drill_basic_xp", 30)
    adv_xp_cfg = await get_game_config_int(db, "drill_advanced_xp", 80)
    recovery_amount = await get_game_config_int(db, "fatigue_recovery_session", 40)
    recovery_energy = await get_game_config_int(db, "fatigue_recovery_energy", 5)

    roster_res = await db.table("player_cards").select("*").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    evo_res = await db.table("active_evolutions").select("card_id").eq("status", "active").execute()
    evo_ids = {e["card_id"] for e in (evo_res.data or [])}
    eligible_players = [p for p in roster if p["id"] not in evo_ids and not p.get("is_retired")]

    cfg = EconomyConfig()
    basic_coins, _basic_energy = drill_cost(60, 5, cfg)
    adv_coins, _adv_energy = drill_cost(60, 12, cfg)
    # Use config-driven energy in UI; package defaults may drift from DB.
    basic_energy = basic_energy_cfg
    adv_energy = adv_energy_cfg

    embed = discord.Embed(
        title="🏋️ Stat Training Drills",
        description=(
            "Spend **action energy** on **Skill Drills** (XP + coins) or a **Recovery Session** "
            "(fatigue restore, **0 XP**, **0 coins**). Both use the same daily drill slots.\n\n"
            f"🏋️ **Training Ground L{tg_level}** — +{max(0, tg_level - 1)} bonus drill XP · "
            f"**+{daily_passive}** daily passive fatigue\n"
            f"⚡ **Action Energy**: `{training_energy}/{max_e}` *(+1 per {int(round(1 / regen_per_min))} min)*\n"
            f"📅 **Daily Drills**: `{daily_count}/{daily_limit}`\n"
            f"💚 **Recovery Session**: `+{recovery_amount}` fatigue · `{recovery_energy}⚡` · 0 coins · 0 XP\n"
            f"💪 **Basic drill** (Lv 1+): `{basic_energy}⚡` + `{basic_coins}` coins @ 60 OVR\n"
            f"💪 **Advanced drill** (Lv {adv_min_level}+): `{adv_energy}⚡` + `{adv_coins}` coins @ 60 OVR"
        ),
        color=0x00FF87,
    )
    embed.set_footer(text="⚡ Energy cost applies")
    if not eligible_players:
        embed.add_field(
            name="No Eligible Players",
            value="All roster cards are locked in an active evolution track.",
            inline=False,
        )

    await edit_ephemeral_hub_message(
        interaction,
        embed,
        StatDrillView(
            owner_id,
            eligible_players[:25],
            tg_level,
            adv_min_level=adv_min_level,
            basic_energy=basic_energy_cfg,
            adv_energy=adv_energy_cfg,
            basic_xp_base=basic_xp_cfg,
            adv_xp_base=adv_xp_cfg,
            recovery_amount=recovery_amount,
            recovery_energy=recovery_energy,
        ),
    )


class StatDrillView(discord.ui.View):
    RECOVERY_DRILL_ID = "__recovery__"

    def __init__(
        self,
        owner_id: int,
        eligible_players: list[dict],
        training_ground_level: int = 1,
        *,
        adv_min_level: int = 10,
        basic_energy: int = 10,
        adv_energy: int = 15,
        basic_xp_base: int = 30,
        adv_xp_base: int = 80,
        recovery_amount: int = 40,
        recovery_energy: int = 5,
    ) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.selected_card_id: str | None = None
        self.selected_drill: str | None = None
        self.eligible_players = eligible_players
        self.training_ground_level = training_ground_level
        self.adv_min_level = int(adv_min_level)
        self.basic_energy = int(basic_energy)
        self.adv_energy = int(adv_energy)
        self.basic_xp_base = int(basic_xp_base)
        self.adv_xp_base = int(adv_xp_base)
        self.recovery_amount = int(recovery_amount)
        self.recovery_energy = int(recovery_energy)
        self._build_items()

    def _selected_player(self) -> dict | None:
        return next(
            (p for p in self.eligible_players if str(p["id"]) == str(self.selected_card_id)),
            None,
        )

    def _recovery_eligible(self, player: dict | None) -> bool:
        if not player:
            return False
        if player.get("injury_tier") or player.get("in_hospital"):
            return False
        return int(player.get("fatigue", 100)) < 100

    def _build_items(self) -> None:
        self.clear_items()
        if self.eligible_players:
            player_options = rebuild_select_options(
                self.eligible_players,
                self.selected_card_id,
                label_fn=lambda p: p["name"],
                description_fn=lambda p: (
                    f"{p['overall']} OVR | Lvl {p['level']} | Fatigue {int(p.get('fatigue', 100))}"
                ),
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

            selected = self._selected_player()
            player_level = int((selected or {}).get("level", 1))
            recovery_ok = self._recovery_eligible(selected)

            drill_options: list[discord.SelectOption] = []
            recovery_desc = (
                f"+{self.recovery_amount} fatigue · 0 XP · {self.recovery_energy}⚡"
            )
            if selected and not recovery_ok:
                if selected.get("injury_tier") or selected.get("in_hospital"):
                    recovery_desc = "Injured — use Hospital"
                elif int(selected.get("fatigue", 100)) >= 100:
                    recovery_desc = "Already fully rested"
            drill_options.append(
                discord.SelectOption(
                    label="💚 Recovery Session",
                    value=self.RECOVERY_DRILL_ID,
                    description=recovery_desc[:100],
                    default=(self.selected_drill == self.RECOVERY_DRILL_ID),
                )
            )
            for drill_id, name in STAT_DRILLS.items():
                tier_xp_base = self.adv_xp_base if player_level >= self.adv_min_level else self.basic_xp_base
                tier_energy = self.adv_energy if player_level >= self.adv_min_level else self.basic_energy
                xp_preview = drill_xp_reward(
                    tier_xp_base,
                    player_level,
                    age=effective_card_age(selected or {}),
                    training_ground_level=self.training_ground_level,
                )
                drill_options.append(
                    discord.SelectOption(
                        label=name,
                        value=drill_id,
                        description=(
                            f"+{xp_preview} XP · {tier_energy}⚡"
                        ),
                        default=(self.selected_drill == drill_id),
                    )
                )
            self.drill_select = discord.ui.Select(
                placeholder="Skill drill or Recovery Session...",
                min_values=1,
                max_values=1,
                options=drill_options,
                row=1,
            )
            self.drill_select.callback = self.drill_select_callback
            self.add_item(self.drill_select)

            is_recovery = self.selected_drill == self.RECOVERY_DRILL_ID
            self.run_btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Recover Fitness ⚡" if is_recovery else "Run Drill ⚡",
                disabled=True,
                row=2,
            )
            self.run_btn.callback = self.run_drill_callback
            self.add_item(self.run_btn)

        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", row=2)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

        self._update_run_btn()

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
        if not hasattr(self, "run_btn"):
            return
        if not (self.selected_card_id and self.selected_drill):
            self.run_btn.disabled = True
            return
        selected = self._selected_player()
        if self.selected_drill == self.RECOVERY_DRILL_ID:
            self.run_btn.disabled = not self._recovery_eligible(selected)
            return
        player_level = int((selected or {}).get("level", 1))
        self.run_btn.disabled = not drill_unlocked(self.selected_drill, player_level)

    async def player_select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_card_id = self.player_select.values[0]
        self._build_items()
        await edit_ephemeral_hub_message(interaction, interaction.message.embeds[0], self)

    async def drill_select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_drill = self.drill_select.values[0]
        self._build_items()
        await edit_ephemeral_hub_message(interaction, interaction.message.embeds[0], self)

    async def run_drill_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            selected_p = next(p for p in self.eligible_players if str(p["id"]) == str(self.selected_card_id))
            if selected_p.get("injury_tier") or selected_p.get("in_hospital"):
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(
                    embed=error_embed(
                        "This player is injured — treat them in Hospital "
                        "(`/profile` → Manage Hospital), not Training Drills."
                    ),
                    ephemeral=True,
                )
                return

            if self.selected_drill == self.RECOVERY_DRILL_ID:
                if int(selected_p.get("fatigue", 100)) >= 100:
                    set_view_controls_disabled(self, disabled=False)
                    await interaction.followup.send(
                        embed=error_embed("That player is already at **full fitness**."),
                        ephemeral=True,
                    )
                    return
                res = await db.rpc("process_recovery_session", {
                    "p_owner_id": self.owner_id,
                    "p_player_card_id": self.selected_card_id,
                }).execute()
                result = res.data or {}
                gained = int(result.get("fatigue_gained", 0) or 0)
                new_fatigue = int(result.get("new_fatigue", selected_p.get("fatigue", 0)) or 0)
                energy_spent = int(result.get("energy_spent", self.recovery_energy) or 0)
                xp_gained = int(result.get("xp_gained", 0) or 0)
                msg = (
                    f"**{selected_p['name']}** completed a **Recovery Session**.\n"
                    f"• Fatigue: `+{gained}` → **{new_fatigue}%**\n"
                    f"• XP gained: `{xp_gained}` (none — fitness over development)\n"
                    f"• Spent: `{energy_spent} energy` + `🪙 0 coins`"
                )
                await interaction.followup.send(embed=success_embed(msg), ephemeral=True)
                await show_training_menu(interaction, self.owner_id)
                return

            res = await db.rpc("process_stat_drill", {
                "p_owner_id": self.owner_id,
                "p_card_id": self.selected_card_id,
                "p_drill_id": self.selected_drill,
            }).execute()
            result = res.data or {}
            parsed = parse_stat_drill_result(result)
            xp_gained = parsed["xp_gained"]
            levels = parsed["levels_gained"]
            skill_pts = parsed["skill_points_granted"]
            new_level = parsed["new_level"]
            new_ovr = result.get("new_ovr", selected_p["overall"])
            coins_spent = parsed["coins_spent"]
            energy_spent = parsed["energy_spent"]

            level_note = ""
            if levels > 0:
                level_note = f"\n• **Level Up!** Now level **{new_level}** (+{skill_pts} skill points)"

            msg = (
                f"**{selected_p['name']}** completed **{STAT_DRILLS.get(self.selected_drill, self.selected_drill)}**.\n"
                f"• XP gained: `+{xp_gained}`{level_note}\n"
                f"• OVR: **{new_ovr}** (unchanged — spend skill points to raise stats)\n"
                f"• Spent: `{energy_spent} energy` + `🪙 {coins_spent:,} coins`"
            )
            await interaction.followup.send(embed=success_embed(msg), ephemeral=True)
            await show_training_menu(interaction, self.owner_id)

        except Exception as exc:
            logger.exception("Failed running stat drill / recovery session.")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


# --- 2. CARD FUSION (sacrifice one card to level up another) ---

async def _fetch_card_locks(owner_id: int) -> tuple[set[str], set[str]]:
    """Returns (starting_11_ids, active_evolution_ids)."""
    db = await get_client()
    assignments_res = await db.table("squad_assignments").select("player_card_id").eq("discord_id", owner_id).execute()
    starting_ids = {str(a["player_card_id"]) for a in (assignments_res.data or [])}
    evo_res = await db.table("active_evolutions").select("card_id").eq("status", "active").execute()
    evo_ids = {str(e["card_id"]) for e in (evo_res.data or [])}
    return starting_ids, evo_ids


async def show_card_fusion_menu(interaction: discord.Interaction, owner_id: int) -> None:
    if not await safe_defer(interaction, ephemeral=True):
        return
    db = await get_client()
    cards_res = await db.table("player_cards").select("*").eq("owner_id", owner_id).order("overall", desc=True).execute()
    cards = cards_res.data or []

    if len(cards) < 2:
        embed = error_embed("You need at least 2 player cards to fuse (one to upgrade and one to sacrifice).")
        await edit_ephemeral_hub_message(interaction, embed, CardFusionView(owner_id, [], []))
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
        await edit_ephemeral_hub_message(interaction, embed, CardFusionView(owner_id, target_pool, sacrifice_pool))
        return

    embed = discord.Embed(
        title="🔥 Card Fusion",
        description=(
            "Sacrifice a **bench card** to feed XP into a **keeper**. The sacrificed card is **permanently deleted**.\n\n"
            "*Sacrifice: not in starting XI or active evolution. "
            "Keeper: not in active evolution.*\n"
            "*Max **3 fusions per day** per club · **200 coins** per fusion.*"
        ),
        color=0xFF6B35,
    )
    embed.add_field(name="Fusion Preview", value="Select keeper and sacrifice to see projected XP.", inline=False)
    embed.set_footer(text="Showing your top 25 eligible cards per role.")
    await edit_ephemeral_hub_message(interaction, embed, CardFusionView(owner_id, target_pool, sacrifice_pool))


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
        embed = self.view._fusion_preview_embed(interaction.message.embeds[0])
        await interaction.response.edit_message(embed=embed, view=self.view)


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
        embed = self.view._fusion_preview_embed(interaction.message.embeds[0])
        await interaction.response.edit_message(embed=embed, view=self.view)


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

            for cid, label in ((self.view.keeper_id, "target"), (self.view.sacrifice_id, "fodder")):
                chk = await db.table("player_cards").select("injury_tier, in_hospital, name").eq(
                    "id", cid
                ).maybe_single().execute()
                row = chk.data if chk else None
                if row and (row.get("injury_tier") or row.get("in_hospital")):
                    await interaction.followup.send(
                        embed=error_embed(
                            f"**{row.get('name', label)}** is injured or in hospital and cannot be used in fusion."
                        ),
                        ephemeral=True,
                    )
                    return

            fusion_res = await db.rpc("train_with_fodder", {
                "p_owner_id": interaction.user.id,
                "p_target_id": self.view.keeper_id,
                "p_fodder_id": self.view.sacrifice_id,
            }).execute()
            fusion = fusion_res.data or {}

            target_res = await db.table("player_cards").select("*").eq("id", self.view.keeper_id).maybe_single().execute()
            keeper = target_res.data
            if not keeper:
                raise ValueError("Could not find the keeper card after fusion.")

            new_level = keeper["level"]
            levels_gained = int(fusion.get("levels_gained", 0))
            fusion_xp = int(fusion.get("fusion_xp", 0))
            skill_pts = int(fusion.get("skill_points_granted", 0))
            progress = f"📈 **Level**: {new_level}\n⭐ **OVR**: {keeper['overall']}\n✨ **Fusion XP**: +{fusion_xp}"
            if levels_gained > 0:
                progress += f"\n🎉 **Level Up!** +{skill_pts} skill points to allocate"

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
            if interaction.message and interaction.response.is_done():
                try:
                    await interaction.followup.edit_message(interaction.message.id, view=self.view)
                except discord.NotFound:
                    pass
            elif interaction.message:
                await interaction.message.edit(view=self.view)
            else:
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

    def _card_by_id(self, pool: list[dict], card_id: str | None) -> dict | None:
        if not card_id:
            return None
        return next((p for p in pool if str(p["id"]) == str(card_id)), None)

    def _fusion_preview_embed(self, embed: discord.Embed) -> discord.Embed:
        embed = embed.copy()
        keeper = self._card_by_id(self.keeper_pool, self.keeper_id)
        sacrifice = self._card_by_id(self.sacrifice_pool, self.sacrifice_id)
        if not keeper or not sacrifice:
            embed.set_field_at(
                0,
                name="Fusion Preview",
                value="Select keeper and sacrifice to see projected XP.",
                inline=False,
            )
            return embed
        fusion_xp = fusion_xp_reward(int(sacrifice.get("level", 1)), int(sacrifice.get("overall", 0)))
        sim = simulate_apply_card_xp(int(keeper.get("xp", 0)), fusion_xp)
        keeper_level = level_from_xp(int(keeper.get("xp", 0)))
        lines = [
            f"**{sacrifice['name']}** → **{keeper['name']}**",
            f"• Fusion XP: **+{fusion_xp}**",
            f"• Projected level: **{keeper_level}** → **{sim.new_level}**",
        ]
        if sim.levels_gained > 0:
            lines.append(f"• **Level Up!** +{sim.skill_points_granted} skill points")
        elif keeper_level >= L_MAX:
            lines.append("• ⚠️ Keeper is max level — XP will be wasted")
        embed.set_field_at(0, name="Fusion Preview", value="\n".join(lines), inline=False)
        return embed


# --- 3. EVOLUTIONS SUB VIEW SYSTEM ---

async def show_club_evolutions_hub(interaction: discord.Interaction, owner_id: int) -> None:
    if not await safe_defer(interaction, ephemeral=True):
        return
    db = await get_client()
    status = await fetch_evolution_hub_status(db, owner_id)
    active = status.get("active") or []

    embed = discord.Embed(
        title="🧬 Evolution Command Center",
        description="Track all active evolution paths for your club.",
        color=0x00FF87,
    )

    slots_label = status.get("slots_label") or f"{len(active)}/{MAX_ACTIVE_EVOLUTIONS} slots used"
    active_count = int(status.get("active_count", len(active)))
    embed.add_field(name="Slots", value=slots_label, inline=True)
    if active_count > MAX_ACTIVE_EVOLUTIONS:
        embed.add_field(
            name="⚠️ Over Slot Limit",
            value=(
                f"**{active_count}** tracks are active but only **{MAX_ACTIVE_EVOLUTIONS}** are allowed. "
                "Cancel excess tracks from **Manage Active** below."
            ),
            inline=False,
        )

    remaining = int(status.get("cooldown_remaining_seconds", 0))
    if status.get("can_cold_start"):
        cooldown_text = "Ready to start a new evolution"
    elif status.get("can_replace"):
        cooldown_text = "Replacement start available (after cancel)"
    else:
        cooldown_text = f"Next evolution available in {format_cooldown_remaining(remaining)}"
    embed.add_field(name="Cooldown", value=cooldown_text, inline=True)

    training_energy = status.get("training_energy", 0)
    energy_max = int(status.get("max_energy", status.get("action_energy_max", 120)) or 120)
    embed.add_field(
        name="Resources",
        value=(
            f"⚡ Training Energy: `{training_energy}/{energy_max}`\n"
            f"💰 Start cost: `{EVOLUTION_START_ENERGY} energy` + `10×OVR` coins per track"
        ),
        inline=False,
    )

    if active:
        lines = []
        for evo in active:
            card_name = evo.get("card_name") or "?"
            track = EVOLUTION_TRACKS.get(evo["evolution_id"], {"name": evo["evolution_id"]})
            played = _evo_played(evo)
            required = _evo_required(evo)
            bar = make_match_progress_bar(played, required)
            ready = " ✅ **READY TO CLAIM**" if played >= required else ""
            lines.append(f"**{card_name}** — {track['name']}\n{bar}{ready}")
        embed.add_field(name=f"Active ({len(active)})", value="\n\n".join(lines), inline=False)
    else:
        embed.add_field(name="Active", value="No players are currently evolving.", inline=False)

    history = status.get("recent_completed") or []
    if history:
        hist_lines = [
            f"**{h.get('card_name', '?')}** — "
            f"{EVOLUTION_TRACKS.get(h['evolution_id'], {}).get('name', h['evolution_id'])}"
            for h in history
        ]
        embed.add_field(name="Recently Completed", value="\n".join(hist_lines), inline=False)

    embed.set_footer(text="⚡ Energy cost applies")

    view = ClubEvolutionsHubView(owner_id, active, status)
    await edit_ephemeral_hub_message(interaction, embed, view)


class ClubEvolutionsHubView(discord.ui.View):
    def __init__(self, owner_id: int, active_evos: list[dict], hub_status: dict | None = None) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.active_evos = active_evos
        self.hub_status = hub_status or {}

        can_start = bool(self.hub_status.get("can_start")) and len(active_evos) < MAX_ACTIVE_EVOLUTIONS
        start_btn = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Start New Evolution ⚡",
            row=0,
            disabled=not can_start,
        )
        start_btn.callback = self.start_new_callback
        self.add_item(start_btn)

        if active_evos:
            options = []
            for evo in active_evos[:25]:
                card_name = evo.get("card_name")
                if not card_name:
                    card = evo.get("player_cards") or {}
                    card_name = card.get("name", "?")
                track = EVOLUTION_TRACKS.get(evo["evolution_id"], {})
                played = _evo_played(evo)
                required = _evo_required(evo)
                options.append(discord.SelectOption(
                    label=f"Cancel: {card_name}",
                    description=f"{track.get('name', '?')} ({played}/{required})",
                    value=evo["id"],
                ))
            cancel_sel = discord.ui.Select(placeholder="Cancel an active evolution...", options=options, row=1)
            cancel_sel.callback = self.cancel_select_callback
            self.add_item(cancel_sel)

        back_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", row=2)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_hub(interaction, self.owner_id)

    async def start_new_callback(self, interaction: discord.Interaction) -> None:
        gate = evolution_start_gate_message(self.hub_status)
        if gate:
            await interaction.response.send_message(embed=error_embed(gate), ephemeral=True)
            return
        await show_evols_menu(interaction, self.owner_id)

    async def cancel_select_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        evo_id = interaction.data["values"][0]
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return
            await db.rpc("cancel_player_evolution", {
                "p_owner_id": self.owner_id,
                "p_evo_id": evo_id,
            }).execute()
            await interaction.followup.send(
                embed=success_embed(
                    f"Evolution cancelled. Progress was reset and **{CANCEL_FEE_COINS} coins** were deducted."
                ),
                ephemeral=True,
            )
            await show_club_evolutions_hub(interaction, self.owner_id)
        except Exception as exc:
            logger.exception("Failed cancelling evolution.")
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


async def show_evols_menu(interaction: discord.Interaction, owner_id: int, preselected_card_id: str | None = None):
    db = await get_client()
    hub_status = await fetch_evolution_hub_status(db, owner_id)
    gate = evolution_start_gate_message(hub_status)

    # 1. Fetch roster
    roster_res = await db.table("player_cards").select("id, name, overall").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    if not roster:
        embed = discord.Embed(title="🧬 Evolutions Hub", description="No players in your roster to evolve.", color=0x00FF87)
        view = EvolutionsSubView(owner_id, None, None, roster, hub_status=hub_status)
        await edit_ephemeral_hub_message(interaction, embed, view)
        return

    # Choose selected card
    target_card_id = preselected_card_id or roster[0]["id"]
    
    card_res = await db.table("player_cards").select("*").eq("id", target_card_id).maybe_single().execute()
    card = card_res.data if card_res else None

    # Fetch active evolution for the card
    evo_res = await db.table("active_evolutions").select("*").eq("card_id", target_card_id).eq("status", "active").maybe_single().execute()
    evo = evo_res.data if evo_res else None

    completed_res = await db.table("active_evolutions").select("evolution_id").eq("card_id", target_card_id).eq("status", "completed").execute()
    completed_tracks = {r["evolution_id"] for r in (completed_res.data or [])}

    energy_cost, coin_cost = evolution_start_cost(card["overall"])

    embed = discord.Embed(
        title=f"🧬 Evolutions: {card['name']}",
        description=f"Current Rating: **{card['overall']} OVR**",
        color=0x00FF87
    )

    if _is_active_evo(evo):
        track = EVOLUTION_TRACKS[evo["evolution_id"]]
        played = _evo_played(evo)
        required = _evo_required(evo)
        embed.add_field(
            name=f"🧬 Active: {track['name']}",
            value=(
                f"{make_match_progress_bar(played, required)}\n"
                f"• Reward: `+{track['reward_val']} {track['reward_stat'].upper()}`"
            ),
            inline=False,
        )
    else:
        if completed_tracks:
            done = [
                f"✅ {EVOLUTION_TRACKS[t]['name']}"
                for t in completed_tracks
                if t in EVOLUTION_TRACKS
            ]
            embed.add_field(
                name="Completed Tracks",
                value="\n".join(done) if done else "None",
                inline=False,
            )
        else:
            embed.add_field(name="Status", value="No active evolution. Pick a track below to start.", inline=False)

        embed.add_field(
            name="Start Cost",
            value=f"⚡ `{energy_cost} training energy` + 🪙 `{coin_cost:,} coins`",
            inline=False,
        )
        if gate:
            embed.add_field(name="Cannot Start", value=gate, inline=False)

    embed.set_footer(text="⚡ Energy cost applies")

    view = EvolutionsSubView(
        owner_id, card, evo, roster, completed_tracks, hub_status=hub_status, start_blocked=bool(gate)
    )
    await edit_ephemeral_hub_message(interaction, embed, view)


class EvolutionsSubView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        card: dict | None,
        active_evo: dict | None,
        roster: list[dict],
        completed_tracks: set[str] | None = None,
        hub_status: dict | None = None,
        start_blocked: bool = False,
    ) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.card = card
        self.active_evo = active_evo
        self.completed_tracks = completed_tracks or set()
        self.hub_status = hub_status or {}
        self.start_blocked = start_blocked

        if roster:
            player_options = [
                discord.SelectOption(label=p["name"], description=f"{p['overall']} OVR", value=p["id"], default=(card and p["id"] == card["id"]))
                for p in roster[:25]
            ]
            player_sel = discord.ui.Select(placeholder="Select card...", options=player_options, row=0)
            player_sel.callback = self.player_select_callback
            self.add_item(player_sel)

        if card and not _is_active_evo(active_evo) and not self.start_blocked:
            energy_cost, coin_cost = evolution_start_cost(card["overall"])
            card_level = int(card.get("level", 1))
            evo_options = []
            for k, track in EVOLUTION_TRACKS.items():
                if k in self.completed_tracks:
                    continue
                min_lvl = track_min_player_level(k)
                if evolution_unlocked(k, card_level):
                    evo_options.append(
                        discord.SelectOption(
                            label=track["name"],
                            description=(
                                f"{energy_cost}⚡ + {coin_cost:,}🪙 | "
                                f"{track['goal']} matches → +{track['reward_val']} {track['reward_stat'].upper()}"
                            ),
                            value=k,
                        )
                    )
                else:
                    evo_options.append(
                        discord.SelectOption(
                            label=f"🔒 {track['name']}",
                            description=f"Requires player Level {min_lvl} (current: {card_level})",
                            value=f"locked_{k}",
                        )
                    )
            if evo_options:
                evo_sel = discord.ui.Select(placeholder="Choose evolution path...", options=evo_options, row=1)
                evo_sel.callback = self.start_evo_callback
                self.add_item(evo_sel)

        if _is_active_evo(active_evo) and _evo_played(active_evo) >= _evo_required(active_evo):
            claim_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="Claim Evolution Reward", row=2)
            claim_btn.callback = self.claim_reward_callback
            self.add_item(claim_btn)

        if _is_active_evo(active_evo) and _evo_played(active_evo) < _evo_required(active_evo):
            cancel_btn = discord.ui.Button(style=discord.ButtonStyle.danger, label=f"Cancel Evolution ({CANCEL_FEE_COINS}🪙)", row=2)
            cancel_btn.callback = self.cancel_evo_callback
            self.add_item(cancel_btn)

        club_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Club Overview", row=3)
        club_btn.callback = self.club_back_callback
        self.add_item(club_btn)

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

    async def club_back_callback(self, interaction: discord.Interaction):
        await show_club_evolutions_hub(interaction, self.owner_id)

    async def player_select_callback(self, interaction: discord.Interaction):
        card_id = interaction.data["values"][0]
        await show_evols_menu(interaction, self.owner_id, preselected_card_id=card_id)

    async def start_evo_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            evo_key = interaction.data["values"][0]
            if evo_key.startswith("locked_"):
                track_id = evo_key.removeprefix("locked_")
                min_lvl = track_min_player_level(track_id)
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(
                    embed=error_embed(f"This evolution requires player Level **{min_lvl}**."),
                    ephemeral=True,
                )
                return
            track = EVOLUTION_TRACKS[evo_key]

            if self.card.get("injury_tier") or self.card.get("in_hospital"):
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(
                    embed=error_embed("Injured players cannot start an evolution track."),
                    ephemeral=True,
                )
                return

            gate = evolution_start_gate_message(self.hub_status)
            if gate:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(embed=error_embed(gate), ephemeral=True)
                return

            res = await db.rpc("start_player_evolution", {
                "p_owner_id": self.owner_id,
                "p_card_id": self.card["id"],
                "p_track_id": evo_key,
            }).execute()
            result = res.data or {}
            energy_spent = result.get("energy_cost", result.get("energy_spent", EVOLUTION_START_ENERGY))
            coins_spent = result.get("coin_cost", result.get("coins_spent", evolution_start_cost(self.card["overall"])[1]))

            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Started!**\n\n"
                    f"**{self.card['name']}** is now on **{track['name']}**.\n"
                    f"• Spent: `{energy_spent} energy` + `🪙 {coins_spent:,} coins`\n"
                    f"• Objective: Play **{track['goal']} matches** with this player in your starting XI.\n"
                    f"• Reward: `+{track['reward_val']} {track['reward_stat'].upper()}`"
                ),
                ephemeral=True,
            )
            await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card["id"])

        except Exception as e:
            logger.exception("Failed starting evolution track.")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(_api_message(e)), ephemeral=True)

    async def cancel_evo_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return
            await db.rpc("cancel_player_evolution", {
                "p_owner_id": self.owner_id,
                "p_evo_id": self.active_evo["id"],
            }).execute()
            await interaction.followup.send(
                embed=success_embed(
                    f"Evolution cancelled for **{self.card['name']}**. "
                    f"Progress reset. **{CANCEL_FEE_COINS} coins** deducted."
                ),
                ephemeral=True,
            )
            await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card["id"])
        except Exception as exc:
            logger.exception("Failed cancelling evolution.")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)

    async def claim_reward_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                set_view_controls_disabled(self, disabled=False)
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                return

            res = await db.rpc("claim_evolution_reward", {
                "p_owner_id": self.owner_id,
                "p_evo_id": self.active_evo["id"],
            }).execute()
            result = res.data or {}
            track = EVOLUTION_TRACKS[self.active_evo["evolution_id"]]
            applied = result.get("reward", track["reward_val"])
            reward_stat = result.get("stat", track["reward_stat"].upper())
            reward_max = int(result.get("reward_max", track["reward_val"]))

            await show_evols_menu(interaction, self.owner_id, preselected_card_id=self.card["id"])
            cap_note = ""
            if result.get("blocked_by_cap"):
                cap_note = "\n*Stat reward skipped — player is already at POT ceiling.*"
            elif applied == 0:
                cap_note = "\n*Stat reward skipped — stat is already at maximum.*"
            elif result.get("reward_clamped"):
                cap_note = (
                    f"\n*Reward clamped to +{applied} {reward_stat} "
                    f"(max +{reward_max}) to respect POT ceiling.*"
                )
            await interaction.followup.send(
                embed=success_embed(
                    f"🧬 **Evolution Completed!**\n\n"
                    f"Claimed rewards for **{self.card['name']}**:\n"
                    f"• **+{applied} {reward_stat}**\n"
                    f"• New Overall: **{result.get('new_ovr', self.card['overall'])} OVR**!"
                    f"{cap_note}"
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.exception("Failed claiming evolution reward.")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(_api_message(e)), ephemeral=True)


# --- 3. SKILL ALLOCATION SUB VIEW SYSTEM ---

async def show_skills_menu(interaction: discord.Interaction, owner_id: int, preselected_card_id: str | None = None):
    if not await safe_defer(interaction, ephemeral=True):
        return
    db = await get_client()
    roster_res = await db.table("player_cards").select("id, name, overall").eq("owner_id", owner_id).order("overall", desc=True).execute()
    roster = roster_res.data or []

    if not roster:
        embed = discord.Embed(title="⭐ Skill Allocation", description="No roster players found.", color=0x00FF87)
        view = SkillsSubView(owner_id, None, roster)
        await edit_ephemeral_hub_message(interaction, embed, view)
        return

    target_card_id = preselected_card_id or roster[0]["id"]
    card_res = await db.table("player_cards").select("*").eq("id", target_card_id).maybe_single().execute()
    card = card_res.data if card_res else None

    skill_pts = int((card or {}).get("skill_points", 0) or 0)
    overall = int((card or {}).get("overall", 0) or 0)
    potential = int((card or {}).get("potential", 0) or 0)
    maxed = overall >= potential and card is not None
    mentor_on = _mentor_enabled()
    mp = sp_to_mentor_units(skill_pts)

    if maxed and mentor_on:
        desc = (
            f"Available Skill Points: **{skill_pts}**\n"
            f"🎓 **Mentor Ready** — converts to **{mp} MP** ({mp * 500} XP)\n\n"
            f"⚡ **PAC**: `{card.get('pac', 50)}` | "
            f"🎯 **SHO**: `{card.get('sho', 50)}` | "
            f"🧠 **PAS**: `{card.get('pas', 50)}`\n"
            f"👟 **DRI**: `{card.get('dri', 50)}` | "
            f"🛡️ **DEF**: `{card.get('def', 50)}` | "
            f"💪 **PHY**: `{card.get('phy', 50)}`"
        )
        if skill_pts <= 0:
            desc += (
                "\n\n_This legend is at potential ceiling. Earn more SP via matches, "
                "then use **Mentor Transfer** to feed your academy._"
            )
        elif skill_pts < 5:
            desc += "\n\n_Need **5 SP** (1 mentor unit) before you can transfer._"
        else:
            desc += "\n\n_Stat allocation is capped — use **Mentor Transfer** to convert surplus SP into youth XP._"
    else:
        desc = (
            f"Available Skill Points: **{skill_pts}**\n\n"
            f"⚡ **PAC**: `{card.get('pac', 50)}` | "
            f"🎯 **SHO**: `{card.get('sho', 50)}` | "
            f"🧠 **PAS**: `{card.get('pas', 50)}`\n"
            f"👟 **DRI**: `{card.get('dri', 50)}` | "
            f"🛡️ **DEF**: `{card.get('def', 50)}` | "
            f"💪 **PHY**: `{card.get('phy', 50)}`"
        )
        if skill_pts <= 0:
            desc += (
                "\n\n_No skill points yet — level up players via **Training Drills** or matches, "
                "then return here to spend points._"
            )

    embed = discord.Embed(
        title=f"⭐ Allocate Skills: {card['name']}",
        description=desc,
        color=0x00FF87,
    )
    view = SkillsSubView(owner_id, card, roster, maxed=maxed and mentor_on)
    await edit_ephemeral_hub_message(interaction, embed, view)


class SkillsSubView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        card: dict | None,
        roster: list[dict],
        *,
        maxed: bool = False,
    ) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.card = card
        self.maxed = maxed

        if roster:
            player_options = [
                discord.SelectOption(
                    label=p["name"],
                    description=f"{p['overall']} OVR",
                    value=p["id"],
                    default=(card and p["id"] == card["id"]),
                )
                for p in roster[:25]
            ]
            player_sel = discord.ui.Select(placeholder="Select card...", options=player_options, row=0)
            player_sel.callback = self.player_select_callback
            self.add_item(player_sel)

        skill_pts = int((card or {}).get("skill_points", 0) or 0)
        if maxed:
            mentor_btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="🎓 Mentor Transfer",
                disabled=skill_pts < 5,
                row=1,
            )
            mentor_btn.callback = self.mentor_callback
            self.add_item(mentor_btn)
        elif card and skill_pts > 0:
            stats = [("pac", "PAC +1"), ("sho", "SHO +1"), ("pas", "PAS +1"), ("dri", "DRI +1"), ("def", "DEF +1"), ("phy", "PHY +1")]
            for idx, (col, label) in enumerate(stats):
                row = 1 if idx < 3 else 2
                btn = SkillPointButton(card["id"], col, label, True, owner_id, row)
                self.add_item(btn)

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

    async def mentor_callback(self, interaction: discord.Interaction) -> None:
        if not self.card:
            return
        await show_mentor_target_menu(interaction, self.owner_id, self.card)


class SkillPointButton(discord.ui.Button):
    def __init__(self, card_id: str, col: str, label: str, active: bool, owner_id: int, row: int) -> None:
        super().__init__(style=discord.ButtonStyle.primary, label=label, disabled=not active, row=row)
        self.card_id = card_id
        self.col = col
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.disabled = True
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
            self.disabled = False
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


# --- 3b. MENTOR TRANSFUSION ---

async def _load_mentor_targets(db, owner_id: int, source_id: str) -> list[dict]:
    res = await db.table("player_cards").select(
        "id, name, overall, potential, level, xp, skill_points"
    ).eq("owner_id", owner_id).order("level").execute()
    rows = res.data or []
    return [
        r for r in rows
        if is_mentor_target(
            overall=int(r.get("overall") or 0),
            potential=int(r.get("potential") or 0),
            level=int(r.get("level") or 1),
            source_id=source_id,
            target_id=str(r["id"]),
        )
    ]


async def show_mentor_target_menu(
    interaction: discord.Interaction,
    owner_id: int,
    source: dict,
) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()
    db = await get_client()
    targets = await _load_mentor_targets(db, owner_id, str(source["id"]))
    if not targets:
        await interaction.followup.send(
            embed=error_embed("No eligible academy targets (need a non-maxed club mate under level 100)."),
            ephemeral=True,
        )
        return
    embed = discord.Embed(
        title=f"🎓 Mentor Transfer — {source['name']}",
        description=(
            f"Source SP: **{int(source.get('skill_points') or 0)}** "
            f"({sp_to_mentor_units(int(source.get('skill_points') or 0))} MP available)\n"
            "Select a developing player to receive mentor XP."
        ),
        color=0x5865F2,
    )
    view = MentorTargetView(owner_id, source, targets)
    await edit_ephemeral_hub_message(interaction, embed, view)


class MentorTargetView(discord.ui.View):
    def __init__(self, owner_id: int, source: dict, targets: list[dict]) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.source = source
        self.targets = targets
        self.selected_id: str | None = None

        options = [
            discord.SelectOption(
                label=t["name"][:100],
                description=f"Lv {t.get('level', 1)} · {t.get('overall', 0)} OVR / {t.get('potential', 0)} POT",
                value=str(t["id"]),
            )
            for t in targets[:25]
        ]
        sel = discord.ui.Select(placeholder="Select target...", options=options, row=0)
        sel.callback = self.select_callback
        self.add_item(sel)

        back = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back", row=1)
        back.callback = self.back_callback
        self.add_item(back)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction) -> None:
        self.selected_id = interaction.data["values"][0]
        target = next((t for t in self.targets if str(t["id"]) == self.selected_id), None)
        if not target:
            await interaction.response.send_message(embed=error_embed("Target not found."), ephemeral=True)
            return
        await show_mentor_amount_menu(interaction, self.owner_id, self.source, target)

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_skills_menu(interaction, self.owner_id, preselected_card_id=str(self.source["id"]))


async def show_mentor_amount_menu(
    interaction: discord.Interaction,
    owner_id: int,
    source: dict,
    target: dict,
) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()
    source_sp = int(source.get("skill_points") or 0)
    target_xp = int(target.get("xp") or 0)
    max_n = mentor_max_units(source_sp, target_xp)
    embed = discord.Embed(
        title="🎓 Choose Mentor Amount",
        description=(
            f"**{source['name']}** → **{target['name']}**\n"
            f"Max transferable now: **{max_n} MP** "
            f"(5 SP = 1 MP = 500 XP)"
        ),
        color=0x5865F2,
    )
    view = MentorAmountView(owner_id, source, target, max_n)
    await edit_ephemeral_hub_message(interaction, embed, view)


class MentorAmountView(discord.ui.View):
    def __init__(self, owner_id: int, source: dict, target: dict, max_n: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.source = source
        self.target = target
        self.max_n = max_n

        for i, n in enumerate((1, 3, 5)):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label=f"{n} MP",
                disabled=n > max_n,
                row=0,
            )
            btn.callback = self._make_amount_cb(n)
            self.add_item(btn)

        max_btn = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label=f"Max ({max_n} MP)" if max_n else "Max",
            disabled=max_n < 1,
            row=0,
        )
        max_btn.callback = self._make_amount_cb(max_n if max_n > 0 else 1)
        self.add_item(max_btn)

        back = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back", row=1)
        back.callback = self.back_callback
        self.add_item(back)

    def _make_amount_cb(self, units: int):
        async def _cb(interaction: discord.Interaction) -> None:
            await show_mentor_confirm(interaction, self.owner_id, self.source, self.target, units)
        return _cb

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_mentor_target_menu(interaction, self.owner_id, self.source)


async def show_mentor_confirm(
    interaction: discord.Interaction,
    owner_id: int,
    source: dict,
    target: dict,
    units: int,
) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()
    preview = preview_mentor_transfer(
        source_sp=int(source.get("skill_points") or 0),
        target_xp=int(target.get("xp") or 0),
        units=units,
    )
    if not preview.valid:
        await interaction.followup.send(
            embed=error_embed(preview.reason or "Cannot preview that transfer."),
            ephemeral=True,
        )
        return

    db = await get_client()
    today = datetime.now(timezone.utc).date().isoformat()
    used_res = await db.table("mentor_transfer_log").select("id", count="exact").eq(
        "club_id", owner_id
    ).eq("transfer_date", today).execute()
    used = int(used_res.count or 0) if used_res else 0
    remaining = max(0, 3 - used)

    embed = discord.Embed(
        title="🎓 Confirm Mentor Transfer",
        description=(
            f"**{source['name']}** → **{target['name']}**\n"
            f"• Mentor units: **{preview.mentor_units} MP**\n"
            f"• SP spent: **{preview.sp_spent}**\n"
            f"• XP granted: **{preview.xp_granted}**\n"
            f"• Level: **{preview.old_level}** → **{preview.new_level}** "
            f"(+{preview.levels_gained}, +{preview.skill_points_granted} SP unlocked)\n"
            f"• Daily transfers remaining: **{remaining}/3**"
        ),
        color=0x5865F2,
    )
    view = MentorConfirmView(owner_id, source, target, units)
    await edit_ephemeral_hub_message(interaction, embed, view)


class MentorConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, source: dict, target: dict, units: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.source = source
        self.target = target
        self.units = units
        self._busy = False

        confirm = discord.ui.Button(style=discord.ButtonStyle.success, label="Confirm Transfer", row=0)
        confirm.callback = self.confirm_callback
        self.add_item(confirm)

        cancel = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", row=0)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        await show_mentor_amount_menu(interaction, self.owner_id, self.source, self.target)

    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if self._busy:
            await interaction.followup.send(
                embed=error_embed("Transfer already in progress."),
                ephemeral=True,
            )
            return
        self._busy = True
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            lock_msg = await assert_not_in_match(db, self.owner_id)
            if lock_msg:
                await interaction.followup.send(embed=error_embed(lock_msg), ephemeral=True)
                self._busy = False
                set_view_controls_disabled(self, disabled=False)
                return

            res = await db.rpc(
                "transfer_mentor_xp",
                {
                    "p_owner_id": self.owner_id,
                    "p_source_card_id": str(self.source["id"]),
                    "p_target_card_id": str(self.target["id"]),
                    "p_mentor_units": self.units,
                },
            ).execute()
            data = res.data if isinstance(res.data, dict) else (res.data[0] if res.data else {})
            xp_result = data.get("xp_result") or {}
            await edit_ephemeral_hub_message(
                interaction,
                success_embed(
                    f"**{self.source['name']}** mentored **{self.target['name']}**\n"
                    f"• Spent **{data.get('sp_spent', self.units * 5)} SP** "
                    f"({data.get('mentor_units', self.units)} MP)\n"
                    f"• Granted **{data.get('xp_granted', self.units * 500)} XP**\n"
                    f"• Level **{xp_result.get('old_level', '?')}** → "
                    f"**{xp_result.get('new_level', '?')}** "
                    f"(+{xp_result.get('levels_gained', 0)})\n"
                    f"• Source SP left: **{data.get('source_skill_points', '?')}**\n"
                    f"• Transfers today: **{data.get('transfers_used_today', '?')}/3** "
                    f"({data.get('transfers_remaining_today', '?')} left)"
                ),
                MentorDoneView(self.owner_id, str(self.source["id"])),
            )
        except Exception as exc:
            logger.exception("Mentor transfer failed.")
            self._busy = False
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(_api_message(exc)), ephemeral=True)


class MentorDoneView(discord.ui.View):
    def __init__(self, owner_id: int, source_id: str) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.source_id = source_id
        back = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Skills", row=0)
        back.callback = self.back_callback
        self.add_item(back)
        hub = discord.ui.Button(style=discord.ButtonStyle.primary, label="Development Hub", row=0)
        hub.callback = self.hub_callback
        self.add_item(hub)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    async def back_callback(self, interaction: discord.Interaction) -> None:
        await show_skills_menu(interaction, self.owner_id, preselected_card_id=self.source_id)

    async def hub_callback(self, interaction: discord.Interaction) -> None:
        await show_hub(interaction, self.owner_id)


# --- COG INTERFACE ---

class DevelopmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="development", description="Development Center: drills, fusion, evolutions, skills, and mentor transfer.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def development(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            player_res = await db.table("players").select("discord_id").eq("discord_id", interaction.user.id).maybe_single().execute()
            if not player_res or not player_res.data:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            await show_hub(interaction, interaction.user.id)

        except Exception as e:
            logger.exception("Failed to load Development Center.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DevelopmentCog(bot))
