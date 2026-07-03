import logging
import asyncio
import discord

from app.db.session import get_session
from app.repositories.guild_config_repository import get_or_create_guild_config
from app.ui.handlers.session import ui_session_manager
from app.services.friendly_service import FriendlyMatchReport
from app.ui.renderers.friendly_live_renderer import FriendlyLiveRenderer
from app.ui.layouts.friendly_live import (
    build_live_kickoff_layout,
    build_live_chunk_layout,
    build_live_halftime_layout,
    build_live_fulltime_layout,
)
from app.ui.components import V2View, container, text_display

logger = logging.getLogger("app.services.friendly_live_playback_service")

class FriendlyLivePlaybackService:
    def __init__(self):
        # Maps session_id (nonce) to asyncio.Task
        self._active_playback_tasks: dict[str, asyncio.Task] = {}
        # Playback sleep duration (configurable for tests)
        self.step_delay_seconds: float = 6.0

    def start_playback(
        self,
        session_id: str,
        report: FriendlyMatchReport,
        interaction: discord.Interaction
    ):
        """
        Spawns the progressive live match thread creation and playback task in the background.
        """
        self.cancel_playback(session_id)
        
        task = asyncio.create_task(
            self._run_playback_loop(session_id, report, interaction)
        )
        self._active_playback_tasks[session_id] = task
        logger.info(f"friendly_playback_task_started: session={session_id}")

    def cancel_playback(self, session_id: str):
        """
        Cancels the active playback task if it exists.
        """
        task = self._active_playback_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(f"friendly_playback_task_cancelled: session={session_id}")

    async def skip_to_full_time(
        self,
        session_id: str,
        report: FriendlyMatchReport,
        interaction: discord.Interaction
    ) -> discord.ui.View:
        """
        Cancels the active playback, marks session as completed, and returns the final Full-Time layout.
        Also schedules thread auto-cleanup.
        """
        self.cancel_playback(session_id)
        
        session_obj = ui_session_manager.get_session(session_id)
        if session_obj:
            session_obj.metadata["status"] = "completed"
            session_obj.metadata["revealed_until_minute"] = 90
            
        home_score = report.home_goals
        away_score = report.away_goals
        events_text = FriendlyLiveRenderer.render_progressive_events(report, 90)
        stats_text = FriendlyLiveRenderer.render_progressive_stats(report, 90)
        
        view = build_live_fulltime_layout(
            report.home_club_name,
            report.away_club_name,
            home_score,
            away_score,
            report.motm_player_name,
            events_text,
            stats_text,
            session_id
        )
        
        # Schedule deferred deletion of thread if thread details are stored
        if session_obj:
            thread_id = session_obj.metadata.get("thread_id")
            starter_msg_id = session_obj.metadata.get("starter_message_id")
            if thread_id and interaction and interaction.guild:
                thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
                if thread:
                    # Notify thread of upcoming deletion
                    try:
                        await thread.send(content="🏁 *This match thread and its logs will be automatically deleted in 2 minutes.*")
                    except Exception:
                        pass
                    
                    starter_msg = None
                    if starter_msg_id:
                        try:
                            parent = thread.parent
                            if parent:
                                starter_msg = await parent.fetch_message(int(starter_msg_id))
                        except Exception:
                            pass
                            
                    asyncio.create_task(self._delete_thread_after_delay(thread, starter_msg, delay_seconds=120))
            
            # Clean up practice session immediately
            if session_obj.metadata.get("type") == "friendly_practice":
                ui_session_manager._sessions.pop(session_id, None)
                
        return view

    async def _run_playback_loop(
        self,
        session_id: str,
        report: FriendlyMatchReport,
        interaction: discord.Interaction
    ):
        thread = None
        starter_msg = None
        
        try:
            home_name = report.home_club_name
            away_name = report.away_club_name
            
            # 1. Initialize Thread
            async with get_session() as session:
                guild_config = await get_or_create_guild_config(session, interaction.guild_id)
                
            channel = interaction.channel
            if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                channel = interaction.guild.system_channel or interaction.guild.text_channels[0]
                
            use_private = guild_config.supports_private_threads is not False
            thread_name = f"⚔️ Friendly — {home_name} vs {away_name}"
            
            if use_private:
                try:
                    thread = await channel.create_thread(
                        name=thread_name,
                        type=discord.ChannelType.private_thread,
                        invitable=False,
                        reason="ElevenBoss friendly match session",
                    )
                except Exception as pe:
                    logger.warning(f"Private thread creation failed for friendly: {pe}. Falling back to public.")
                    use_private = False
                    
            if not use_private:
                starter_msg = await channel.send(
                    f"📋 Setting up friendly match thread between **{home_name}** and **{away_name}**..."
                )
                thread = await starter_msg.create_thread(
                    name=thread_name,
                    reason="ElevenBoss friendly match session",
                )
                
            # Store thread details in session
            session_obj = ui_session_manager.get_session(session_id)
            if session_obj:
                session_obj.metadata["thread_id"] = thread.id
                if starter_msg:
                    session_obj.metadata["starter_message_id"] = starter_msg.id
                    
            # 2. Add Users to Thread
            if session_obj:
                # Add Challenger
                challenger_id = session_obj.metadata.get("challenger_user_id") or session_obj.discord_user_id
                try:
                    challenger_member = interaction.guild.get_member(challenger_id) or await interaction.guild.fetch_member(challenger_id)
                    if challenger_member:
                        await thread.add_user(challenger_member)
                except Exception as ae:
                    logger.warning(f"Failed to add challenger {challenger_id} to friendly thread: {ae}")
                    
                # Add Opponent (if challenge mode)
                opponent_id = session_obj.metadata.get("opponent_user_id")
                if opponent_id:
                    try:
                        opponent_member = interaction.guild.get_member(opponent_id) or await interaction.guild.fetch_member(opponent_id)
                        if opponent_member:
                            await thread.add_user(opponent_member)
                    except Exception as ae:
                        logger.warning(f"Failed to add opponent {opponent_id} to friendly thread: {ae}")
                        
            # 3. Edit Main Channel Message to Redirect
            redirect_view = V2View([
                container([
                    text_display(
                        f"⚔️ **Friendly Match Accepted!**\n\n"
                        f"Follow the live progressive match action inside the thread: {thread.mention}"
                    )
                ])
            ])
            await interaction.edit_original_response(view=redirect_view)
            
            # 4. Start Live Playback inside Thread
            # Send initial message inside thread which we will progressively edit
            loading_view = V2View([
                container([
                    text_display("⏱️ *Loading match engine playback...*")
                ])
            ])
            thread_msg = await thread.send(view=loading_view)
            if session_obj:
                session_obj.metadata["thread_msg_id"] = thread_msg.id
                
            steps = [0, 15, 30, 45, 60, 75, 90]
            for step in steps:
                session_obj = ui_session_manager.get_session(session_id)
                if not session_obj:
                    break
                    
                status = session_obj.metadata.get("status")
                if status in ("completed", "cancelled", "declined"):
                    break
                    
                session_obj.metadata["revealed_until_minute"] = step
                home_score, away_score = FriendlyLiveRenderer.get_score_at_minute(report, step)
                events_text = FriendlyLiveRenderer.render_progressive_events(report, step)
                
                if step == 0:
                    view = build_live_kickoff_layout(home_name, away_name, session_id)
                    session_obj.metadata["status"] = "playing"
                elif step == 45:
                    stats_text = FriendlyLiveRenderer.render_progressive_stats(report, 45)
                    view = build_live_halftime_layout(home_name, away_name, home_score, away_score, events_text, stats_text, session_id)
                    session_obj.metadata["status"] = "half_time"
                elif step == 90:
                    stats_text = FriendlyLiveRenderer.render_progressive_stats(report, 90)
                    view = build_live_fulltime_layout(home_name, away_name, home_score, away_score, report.motm_player_name, events_text, stats_text, session_id)
                    session_obj.metadata["status"] = "completed"
                else:
                    view = build_live_chunk_layout(home_name, away_name, home_score, away_score, step, events_text, session_id)
                    session_obj.metadata["status"] = "playing"
                    
                try:
                    await thread_msg.edit(view=view)
                except Exception as de:
                    logger.warning(f"Failed to edit progressive thread message for step {step}: {de}")
                    break
                    
                if step < 90:
                    await asyncio.sleep(self.step_delay_seconds)
                    
            # 5. Thread Complete: Schedule auto-cleanup
            session_obj = ui_session_manager.get_session(session_id)
            if session_obj:
                session_obj.metadata["status"] = "completed"
                
            try:
                await thread.send(content="🏁 *This match thread and its logs will be automatically deleted in 2 minutes.*")
            except Exception:
                pass
                
            asyncio.create_task(self._delete_thread_after_delay(thread, starter_msg, delay_seconds=120))
            
            # Clean up practice session
            if session_obj and session_obj.metadata.get("type") == "friendly_practice":
                ui_session_manager._sessions.pop(session_id, None)
                
            self._active_playback_tasks.pop(session_id, None)
            
        except asyncio.CancelledError:
            logger.info(f"Playback task for session {session_id} was cancelled.")
            self._active_playback_tasks.pop(session_id, None)
        except Exception as e:
            logger.error(f"Error in friendly match playback loop: {e}", exc_info=e)
            self._active_playback_tasks.pop(session_id, None)

    async def _delete_thread_after_delay(
        self,
        thread: discord.Thread,
        starter_msg: discord.Message | None,
        delay_seconds: int = 120
    ):
        """
        Waits for delay_seconds then deletes the friendly match thread and its public starter message.
        """
        await asyncio.sleep(delay_seconds)
        try:
            if starter_msg:
                try:
                    await starter_msg.delete()
                except Exception:
                    pass
            await thread.delete()
            logger.info(f"Deleted friendly match thread {thread.id} after delay.")
        except Exception as e:
            logger.warning(f"Failed to delete friendly match thread {thread.id}: {e}")

# Global singleton playback service
friendly_playback_service = FriendlyLivePlaybackService()
