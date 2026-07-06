# apps/discord_bot/cogs/onboarding_cog.py
from __future__ import annotations
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
from supabase import Client

from gacha import generate_starter_squad
from apps.discord_bot.db.client import get_client
from apps.discord_bot.core.thread_manager import ThreadManager
from apps.discord_bot.embeds.onboarding_embeds import (
    welcome_thread_embed,
    club_confirmation_embed,
    recruitment_embed,
    marquee_reveal_embed,
    registration_complete_embed
)
from apps.discord_bot.embeds.common_embeds import error_embed

logger = logging.getLogger(__name__)

ANIMATION_STEPS = [
    (0.0,  "🔎 Scouting the transfer market for your Marquee signing..."),
    (1.5,  "📋 Reviewing elite player dossiers..."),
    (1.5,  "🤝 Initiating contract negotiations..."),
    (1.5,  "❌ Rejected! Agent demands too high. Moving on..."),
    (2.0,  "🤝 New target found. Making an offer..."),
    (1.5,  "⏳ Waiting for a response..."),
    (2.0,  "✅ SIGNED! Your club's Captain has arrived!"),
]

class ClubSetupModal(discord.ui.Modal, title="Set Up Your Club"):
    club_name = discord.ui.TextInput(
        label="Club Name",
        placeholder="e.g. FC Midnight",
        max_length=32,
        required=True,
    )
    manager_name = discord.ui.TextInput(
        label="Manager Name",
        placeholder="e.g. Sir Alex",
        max_length=24,
        required=True,
    )

    def __init__(self) -> None:
        super().__init__()
        self.submitted_club: str = ""
        self.submitted_manager: str = ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.submitted_club = self.club_name.value.strip()
        self.submitted_manager = self.manager_name.value.strip()
        await interaction.response.defer()


def _valid_club_details(club: str, manager: str) -> str | None:
    if not club:
        return "Club name cannot be empty or whitespace only."
    if not manager:
        return "Manager name cannot be empty or whitespace only."
    return None


class WelcomeView(discord.ui.View):
    def __init__(self, owner_id: int, thread_manager: ThreadManager, db: Client, user: discord.Member | discord.User) -> None:
        super().__init__(timeout=3600)  # 60-minute view timeout
        self.owner_id = owner_id
        self.thread_manager = thread_manager
        self.db = db
        self.user = user
        self.message: discord.Message | None = None
        self._setup_started = False

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Begin Setup →", style=discord.ButtonStyle.primary, emoji="⚽")
    async def begin(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.thread_manager.check_owner(interaction, self.owner_id):
            await interaction.response.send_message(
                "This setup wizard belongs to another player.", ephemeral=True
            )
            return
        if self._setup_started:
            await interaction.response.send_message("Setup already in progress.", ephemeral=True)
            return
        self._setup_started = True

        modal = ClubSetupModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        err = _valid_club_details(modal.submitted_club, modal.submitted_manager)
        if err:
            self._setup_started = False
            await interaction.followup.send(embed=error_embed(err), ephemeral=True)
            return

        if self.message:
            button.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

        view = ConfirmationView(
            owner_id=self.owner_id,
            thread_manager=self.thread_manager,
            club_name=modal.submitted_club,
            manager_name=modal.submitted_manager,
            db=self.db,
            user=self.user,
        )
        confirm_msg = await interaction.followup.send(
            embed=club_confirmation_embed(modal.submitted_club, modal.submitted_manager),
            view=view,
        )
        view.message = confirm_msg
        self.stop()

class ConfirmationView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        thread_manager: ThreadManager,
        club_name: str,
        manager_name: str,
        db: Client,
        user: discord.User | discord.Member,
    ) -> None:
        super().__init__(timeout=3600)
        self.owner_id = owner_id
        self.thread_manager = thread_manager
        self.club_name = club_name
        self.manager_name = manager_name
        self.db = db
        self.user = user
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Confirm Club", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.thread_manager.check_owner(interaction, self.owner_id):
            await interaction.response.send_message(
                "This setup wizard belongs to another player.", ephemeral=True
            )
            return

        # Disable buttons immediately to prevent double click
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

        existing = await self.db.table("players").select("discord_id").eq("discord_id", self.owner_id).maybe_single().execute()
        if existing and existing.data:
            await interaction.followup.send(
                embed=error_embed("You're already registered! This setup room will close shortly."),
                ephemeral=True,
            )
            return

        err = _valid_club_details(self.club_name, self.manager_name)
        if err:
            await interaction.followup.send(embed=error_embed(err), ephemeral=True)
            return

        # Run animation
        await _run_recruitment_animation(
            message=self.message,
            thread=interaction.channel,  # type: ignore
            club_name=self.club_name,
            manager_name=self.manager_name,
            owner_id=self.owner_id,
            thread_manager=self.thread_manager,
            db=self.db,
            user=self.user
        )
        self.stop()

    @discord.ui.button(label="Edit Details", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.thread_manager.check_owner(interaction, self.owner_id):
            await interaction.response.send_message(
                "This setup wizard belongs to another player.", ephemeral=True
            )
            return

        modal = ClubSetupModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        err = _valid_club_details(modal.submitted_club, modal.submitted_manager)
        if err:
            await interaction.followup.send(embed=error_embed(err), ephemeral=True)
            return

        self.club_name = modal.submitted_club
        self.manager_name = modal.submitted_manager

        if self.message:
            await self.message.edit(
                embed=club_confirmation_embed(self.club_name, self.manager_name),
                view=self
            )

async def _run_recruitment_animation(
    message: discord.Message,
    thread: discord.Thread,
    club_name: str,
    manager_name: str,
    owner_id: int,
    thread_manager: ThreadManager,
    db: Client,
    user: discord.Member | discord.User,
) -> None:
    try:
        # Phase 1: Run animation steps
        for delay, text in ANIMATION_STEPS:
            if delay > 0:
                await asyncio.sleep(delay)
            await message.edit(embed=recruitment_embed(text), view=None)

        # Phase 2: Generate full 11-player starter squad (pure package logic, no discord)
        squad = generate_starter_squad()          # returns StarterSquad
        marquee = squad.marquee                   # Rare/Epic Captain
        all_players = squad.all_players           # 11 ordered GK->DEF->MID->FWD

        # Phase 3: Show Marquee Reveal embed (Captain spotlight)
        await asyncio.sleep(0.5)
        await message.edit(embed=marquee_reveal_embed(marquee))
        await asyncio.sleep(2.5)

        # Phase 4: Execute atomic Supabase transaction (all 11 players + squad slots)
        cards_payload = [
            {
                "name":        p.name,
                "position":    p.position,
                "rarity":      p.rarity,
                "base_rating": p.base_rating,
                "overall":     p.overall,
                "pac":         p.pac,
                "sho":         p.sho,
                "pas":         p.pas,
                "dri":         p.dri,
                "def":         p.def_stat,
                "phy":         p.phy,
                "potential":   p.potential,
                "age":         p.age,
            }
            for p in all_players
        ]
        await db.rpc("register_new_player", {
            "p_discord_id":   owner_id,
            "p_username":     str(user),
            "p_club_name":    club_name,
            "p_manager_name": manager_name,
            "p_cards":        cards_payload,     # JSON array of 11 card dicts
        }).execute()

        # Phase 5: Send Registration Complete embeds and schedule thread deletion
        embeds = registration_complete_embed(marquee, squad.youth, club_name, manager_name)
        countdown_msg = await thread.send(
            embeds=embeds
        )
        # Delete thread after 10s countdown
        await thread_manager.delete_thread_after(thread, delay_seconds=10, countdown_message=countdown_msg)

    except Exception as e:
        logger.exception("Onboarding failed due to an error.")
        msg = str(e)
        if "ALREADY_REGISTERED" in msg:
            user_msg = "You're already registered as a manager. This setup room will close shortly."
        else:
            user_msg = f"Setup failed: {msg}\n\nThis setup room will close in 15 seconds to prevent orphaned threads."
        try:
            err_msg = await thread.send(embed=error_embed(user_msg))
            await thread_manager.delete_thread_after(thread, delay_seconds=15, countdown_message=err_msg)
        except Exception:
            pass

class OnboardingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="register", description="Register your football club and sign your starting squad.")
    @app_commands.guild_only()
    async def register(self, interaction: discord.Interaction) -> None:
        # Check registration
        db = await get_client()
        result = await db.table("players").select("discord_id, club_name, manager_name").eq("discord_id", interaction.user.id).maybe_single().execute()
        if result and result.data:
            club = result.data.get("club_name")
            manager = result.data.get("manager_name")
            await interaction.response.send_message(
                f"You're already registered as Manager **{manager}** of **{club}**!",
                ephemeral=True
            )
            return

        # Defer and create onboarding thread
        await interaction.response.defer(ephemeral=True)
        
        try:
            # We assume thread_manager is attached to the bot singleton
            thread_manager: ThreadManager = getattr(self.bot, "thread_manager")
            thread = await thread_manager.create_onboarding_thread(interaction, interaction.user.id)
            
            welcome_embed = welcome_thread_embed(interaction.user.display_name)
            view = WelcomeView(interaction.user.id, thread_manager, db, interaction.user)
            thread_msg = await thread.send(embed=welcome_embed, view=view)
            view.message = thread_msg
            
            await interaction.followup.send(
                f"Your private setup room is ready: {thread.mention}",
                ephemeral=True
            )
        except Exception as e:
            logger.exception("Failed to start onboarding room.")
            await interaction.followup.send(
                f"Failed to create setup room: {str(e)}",
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingCog(bot))
