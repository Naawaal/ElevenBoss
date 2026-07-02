"""
OnboardingService — orchestrates the full guided registration flow.
Owns session lifecycle, club creation, squad generation, and completion.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
import discord
from sqlalchemy.exc import IntegrityError
from app.db.session import get_session
from app.models.onboarding_session import OnboardingSession
from app.onboarding.steps import OnboardingStep, next_step
from app.repositories import get_or_create_guild_config, get_manager_by_discord_id
from app.repositories.manager_repository import create_manager
from app.repositories import onboarding_repository as onb_repo
from app.services.club_service import ClubService, ClubNameError, ClubNameTakenError
from app.services.player_service import PlayerService
from app.services.onboarding_thread_factory import create_onboarding_thread
from app.onboarding import renderers
from app.error_reporting import capture_exception

logger = logging.getLogger("app.services.onboarding_service")

IS_COMPONENTS_V2 = 32768  # discord IS_COMPONENTS_V2 flag value (1 << 15)


class OnboardingService:

    # ── Entry point ────────────────────────────────────────────────────────

    @staticmethod
    async def start_or_resume_registration(interaction: discord.Interaction) -> None:
        """
        Main entry for /register. Always called after interaction.response.defer().
        Decision tree:
          1. User already has a club  → ephemeral error
          2. User has ACTIVE/COMPLETING session with valid thread  → nudge + resume
          3. User has session with bad/missing thread  → repair
          4. No session  → create DB reservation → create thread → send step 1
        """
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        async with get_session() as session:
            # 1. Check for existing club
            existing_club = await ClubService.get_user_club(guild_id, user_id, session)
            if existing_club:
                await interaction.followup.send(
                    f"You already manage **{existing_club.name}**! "
                    f"Use `/locker` to open your club dashboard.",
                    ephemeral=True,
                )
                return

            # 2. Check for active onboarding session
            onb_session = await onb_repo.get_active_session(session, guild_id, user_id)
            guild_config = await get_or_create_guild_config(session, guild_id)

            if onb_session:
                if onb_session.thread_id:
                    # Try to resolve the thread
                    try:
                        thread = interaction.client.get_channel(int(onb_session.thread_id))
                        if thread is None:
                            thread = await interaction.client.fetch_channel(
                                int(onb_session.thread_id)
                            )
                        if isinstance(thread, discord.Thread) and not thread.archived:
                            # Valid session — redirect user
                            await interaction.followup.send(
                                f"You have an active setup session in {thread.mention}. "
                                "Head there to continue your registration!",
                                ephemeral=True,
                            )
                            return
                    except (discord.NotFound, discord.HTTPException):
                        pass  # Thread gone — fall through to repair

                # Session exists but thread is missing/archived → repair
                logger.info(
                    f"onboarding_repair: session={onb_session.id}, user={user_id}"
                )
                # Clean up any other duplicate/stale threads/sessions first
                await OnboardingService.cleanup_old_threads_and_sessions(
                    interaction=interaction,
                    db_session=session,
                    active_session_id=onb_session.id,
                )
                # Reset the session to WELCOME and re-create thread
                onb_session.current_step = OnboardingStep.WELCOME
                onb_session.last_activity_at = datetime.now(timezone.utc)
                await session.flush()
                await OnboardingService._create_thread_and_send_step(
                    interaction=interaction,
                    db_session=session,
                    onb_session=onb_session,
                    guild_config=guild_config,
                )
                return

            # Clean up any duplicate/stale threads/sessions before creating a new one
            await OnboardingService.cleanup_old_threads_and_sessions(
                interaction=interaction,
                db_session=session,
            )

            # 3. No existing session — create DB reservation first
            try:
                onb_session = await onb_repo.create_active_reservation(
                    session, guild_id, user_id, interaction.channel_id
                )
                await session.flush()
            except IntegrityError:
                await session.rollback()
                await interaction.followup.send(
                    "It looks like you're already starting a registration. "
                    "Please wait a moment and try again.",
                    ephemeral=True,
                )
                return

            await OnboardingService._create_thread_and_send_step(
                interaction=interaction,
                db_session=session,
                onb_session=onb_session,
                guild_config=guild_config,
            )

    @staticmethod
    async def cleanup_old_threads_and_sessions(
        interaction: discord.Interaction,
        db_session,
        active_session_id: uuid.UUID | None = None,
    ) -> None:
        """
        Clean up any stale/unfinished onboarding threads and database sessions
        for the user to prevent duplicate threads and DB clutter.
        """
        from sqlalchemy import select
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        # 1. Query DB for any sessions for this user in this guild that are not COMPLETED
        # and are not the current active_session_id (if any).
        from app.repositories.onboarding_repository import STATUS_COMPLETED, STATUS_ABANDONED
        stmt = select(OnboardingSession).where(
            OnboardingSession.guild_id == str(guild_id),
            OnboardingSession.user_id == str(user_id),
            OnboardingSession.status != STATUS_COMPLETED,
        )
        if active_session_id:
            stmt = stmt.where(OnboardingSession.id != active_session_id)

        result = await db_session.execute(stmt)
        old_sessions = list(result.scalars().all())

        for old_sess in old_sessions:
            # Archive the thread if we have its ID
            if old_sess.thread_id:
                try:
                    await renderers.archive_thread(
                        interaction.client,
                        old_sess.thread_id,
                        delete_starter_message_id=old_sess.starter_message_id,
                    )
                except Exception as e:
                    logger.warning(
                        f"cleanup_old_threads_and_sessions: failed to archive thread {old_sess.thread_id}: {e}"
                    )

            # Mark the session as ABANDONED in DB
            old_sess.status = STATUS_ABANDONED
            now_time = datetime.now(timezone.utc)
            old_sess.cleanup_after = now_time
            old_sess.abandoned_at = now_time
            old_sess.last_activity_at = now_time
            db_session.add(old_sess)

        await db_session.flush()

        # 2. Proactively scan Discord guild active threads for any thread named
        # "⚽ Registration — {user.display_name}" that isn't the active one.
        # This acts as a fallback for sessions that crashed before saving thread_id to the DB.
        try:
            guild = interaction.guild
            if guild:
                target_name = f"⚽ Registration — {interaction.user.display_name}"
                active_threads = await guild.active_threads()

                # Retrieve active session's thread ID to avoid archiving it
                active_thread_id = None
                if active_session_id:
                    stmt = select(OnboardingSession).where(OnboardingSession.id == active_session_id)
                    res = await db_session.execute(stmt)
                    active_sess = res.scalar_one_or_none()
                    if active_sess:
                        active_thread_id = active_sess.thread_id

                for thread in active_threads:
                    if thread.name == target_name:
                        if active_thread_id and str(thread.id) == str(active_thread_id):
                            continue

                        try:
                            await thread.edit(archived=True)
                            logger.info(f"cleanup_old_threads_and_sessions: archived dangling thread {thread.id}")
                        except Exception as e:
                            logger.warning(f"cleanup_old_threads_and_sessions: failed to archive dangling thread {thread.id}: {e}")
        except Exception as e:
            logger.warning(f"cleanup_old_threads_and_sessions: Discord thread scan failed: {e}")

    # ── Internal: thread creation & first step ─────────────────────────────

    @staticmethod
    async def _create_thread_and_send_step(
        interaction: discord.Interaction,
        db_session,
        onb_session: OnboardingSession,
        guild_config,
    ) -> None:
        """Create the Discord thread and deliver the first step message."""
        try:
            thread_result = await create_onboarding_thread(
                interaction, db_session, guild_config
            )
        except RuntimeError as e:
            await onb_repo.mark_failed(db_session, onb_session.id, str(e))
            await interaction.followup.send(str(e), ephemeral=True)
            return

        await onb_repo.attach_thread(
            db_session,
            onb_session.id,
            thread_result.thread_id,
            thread_result.starter_message_id,
            thread_result.mode,
        )

        # Reload the session so renderers see the thread_id
        onb_session.thread_id = str(thread_result.thread_id)
        onb_session.thread_mode = thread_result.mode

        # Add user to the private thread
        if thread_result.mode == "PRIVATE":
            try:
                await thread_result.thread.add_user(interaction.user)
            except discord.HTTPException:
                pass  # Not critical

        # Send visibility warning if public
        if thread_result.visibility_warning:
            try:
                await thread_result.thread.send(thread_result.visibility_warning)
            except discord.HTTPException:
                pass

        await interaction.followup.send(
            f"Your registration setup is ready! Head to {thread_result.thread.mention} to get started.",
            ephemeral=True,
        )

        # Send the first step into the thread
        await renderers.send_current_step(
            interaction.client, onb_session.thread_id, onb_session
        )

    # ── Interaction handlers ────────────────────────────────────────────────

    @staticmethod
    async def handle_next_step(
        interaction: discord.Interaction,
        session_id: uuid.UUID,
        current_step: str,
    ) -> None:
        """
        Handle a 'next' button click. Validates ownership, advances the step,
        and renders the next screen.
        """
        await interaction.response.defer()
        async with get_session() as session:
            onb_session = await onb_repo.get_for_update(session, session_id)
            if not onb_session:
                await interaction.followup.send(
                    "This setup session has expired. Please run `/register` again.",
                    ephemeral=True,
                )
                return

            # Ownership check
            if str(onb_session.user_id) != str(interaction.user.id):
                await interaction.followup.send(
                    "This registration session doesn't belong to you.",
                    ephemeral=True,
                )
                return

            # Stale-step guard: the button's step must match the session's current step
            if onb_session.current_step != current_step:
                # Re-render the actual current step so buttons are fresh
                await renderers.send_current_step(
                    interaction.client, onb_session.thread_id, onb_session
                )
                return

            nxt = next_step(current_step)
            if nxt is None:
                return

            onb_session.current_step = nxt
            onb_session.last_activity_at = datetime.now(timezone.utc)

            await renderers.send_current_step(
                interaction.client, onb_session.thread_id, onb_session
            )

    @staticmethod
    async def handle_club_name_modal(
        interaction: discord.Interaction,
        session_id: uuid.UUID,
        raw_name: str,
    ) -> None:
        """
        Called from ClubNameModal.on_submit. Validates the name, saves it,
        and advances to EXPLAIN_NEXT_STEPS.
        """
        await interaction.response.defer()
        async with get_session() as session:
            onb_session = await onb_repo.get_for_update(session, session_id)
            if not onb_session:
                await interaction.followup.send(
                    "This setup session has expired. Please run `/register` again.",
                    ephemeral=True,
                )
                return

            if str(onb_session.user_id) != str(interaction.user.id):
                await interaction.followup.send(
                    "This modal doesn't belong to you.",
                    ephemeral=True,
                )
                return

            # Validate name
            try:
                display_name = ClubService.validate_club_name(raw_name)
            except ClubNameError as e:
                await renderers.send_current_step(
                    interaction.client,
                    onb_session.thread_id,
                    onb_session,  # stays on COLLECT_CLUB_NAME with error
                )
                # Send inline error
                from app.ui.components import V2View
                from app.onboarding.embeds import build_collect_club_name
                error_view = V2View(
                    build_collect_club_name(session_id, error=str(e))
                )
                try:
                    thread = interaction.client.get_channel(int(onb_session.thread_id))
                    if thread:
                        await thread.send(view=error_view)
                except Exception:
                    pass

                return

            # Uniqueness check
            normalized = ClubService.normalize_club_name(display_name)
            exists = await ClubService.club_name_exists(
                interaction.guild_id, normalized, session
            )
            if exists:
                await renderers.send_name_taken_retry(
                    interaction.client, onb_session, display_name
                )
                return

            # Save collected data and advance step by modifying the ORM instance directly
            onb_session.current_step = OnboardingStep.RECRUIT_PLAYERS
            onb_session.last_activity_at = datetime.now(timezone.utc)
            curr_data = dict(onb_session.collected_data or {})
            curr_data["club_name"] = display_name
            onb_session.collected_data = curr_data

            await renderers.send_current_step(
                interaction.client, onb_session.thread_id, onb_session
            )

    @staticmethod
    async def handle_finish(
        interaction: discord.Interaction,
        session_id: uuid.UUID,
    ) -> None:
        """
        Handle the 'Finish Setup' button click. Advances the session to COMPLETE
        then kicks off completion.
        """
        await interaction.response.defer()
        club_name = "Your Club"
        async with get_session() as session:
            onb_session = await onb_repo.get_for_update(session, session_id)
            if not onb_session:
                await interaction.followup.send(
                    "This setup session has expired. Please run `/register` again.",
                    ephemeral=True,
                )
                return

            if str(onb_session.user_id) != str(interaction.user.id):
                await interaction.followup.send(
                    "This registration session doesn't belong to you.",
                    ephemeral=True,
                )
                return

            club_name = onb_session.collected_data.get("club_name", "Your Club")
            # Advance to COMPLETE so claim_completion works
            onb_session.current_step = OnboardingStep.COMPLETE
            onb_session.last_activity_at = datetime.now(timezone.utc)

        # Immediately edit original response to show loading card!
        try:
            from app.ui.components import V2View
            from app.onboarding import embeds
            loading_view = V2View(embeds.build_loading_screen(club_name))
            await interaction.edit_original_response(view=loading_view)
        except Exception as e:
            logger.warning(f"handle_finish: failed to edit original response to loading screen: {e}")

        await OnboardingService.complete_registration(
            bot=interaction.client,
            session_id=session_id,
            guild_id=interaction.guild_id,
            interaction=interaction,
        )


    # ── Completion orchestration ────────────────────────────────────────────

    @staticmethod
    async def complete_registration(
        bot: discord.Client,
        session_id: uuid.UUID,
        guild_id: int | str,
        interaction: discord.Interaction | None = None,
    ) -> None:
        """
        Idempotent completion: claim → ensure_club_created → create_squad → mark_completed.
        Safe to retry if interrupted mid-way.
        """
        async with get_session() as session:
            # Atomic claim: only one concurrent call succeeds
            claimed = await onb_repo.claim_completion(session, session_id)
            onb_session = await onb_repo.get_for_update(session, session_id)

            if not onb_session:
                logger.error(f"complete_registration: session {session_id} not found")
                return

            if not claimed and onb_session.status != "COMPLETING":
                # Another call is handling this; skip
                logger.info(f"complete_registration: session {session_id} already completed/claimed")
                return

        # Ensure club & manager are created (idempotent)
        club_id = await OnboardingService._ensure_club_created(session_id, guild_id)
        if club_id is None:
            # Rolled back — re-read and get club_id
            async with get_session() as session:
                onb_session = await onb_repo.get_session_by_id(session, session_id)
                if onb_session and onb_session.club_id:
                    club_id = onb_session.club_id
                else:
                    logger.error(f"complete_registration: could not obtain club_id for session {session_id}")
                    return

        # Generate squad (idempotent)
        players = []
        try:
            async with get_session() as session:
                result = await PlayerService.create_squad(
                    club_id, session, seed=f"onboarding:{session_id}"
                )
                logger.info(
                    f"complete_registration: squad {result.status} for club {club_id}"
                )
                players = result.players
        except Exception as exc:
            capture_exception(exc)
            logger.error(f"complete_registration: squad generation failed: {exc}", exc_info=exc)
            async with get_session() as session:
                await onb_repo.mark_failed(session, session_id, str(exc))
            if interaction:
                try:
                    from app.ui.components import V2View, container, text_display
                    error_view = V2View([
                        container([
                            text_display(f"❌ **Squad recruitment failed**: {exc}\n\nOur team has been notified. Please try `/register` again.")
                        ])
                    ])
                    await interaction.edit_original_response(view=error_view)
                except Exception:
                    pass
            return

        # Mark completed and schedule cleanup
        cleanup_after = datetime.now(timezone.utc) + timedelta(seconds=12)
        async with get_session() as session:
            await onb_repo.mark_completed(session, session_id, club_id, cleanup_after)
            onb_session = await onb_repo.get_session_by_id(session, session_id)

        # Render success
        if onb_session:
            club_name = onb_session.collected_data.get("club_name", "Your Club")
            if interaction:
                try:
                    from app.ui.components import V2View
                    from app.onboarding import views as step_views
                    view = step_views.success_view(club_name, players=players)
                    await interaction.edit_original_response(view=view)
                except Exception as e:
                    logger.warning(f"complete_registration: failed to edit original response: {e}")
                    await renderers.send_success(bot, onb_session, club_name, players=players)
            else:
                await renderers.send_success(bot, onb_session, club_name, players=players)

            # Schedule thread archiving
            import asyncio
            asyncio.create_task(
                OnboardingService._deferred_archive(bot, onb_session, delay_seconds=12)
            )

    @staticmethod
    async def _ensure_club_created(
        session_id: uuid.UUID, guild_id: int | str
    ) -> uuid.UUID | None:
        """
        SELECT FOR UPDATE on the session; if club_id is already set, return it.
        Otherwise create the manager + club atomically and persist club_id on the session.
        Returns the club UUID, or None on failure (caller re-reads).
        """
        async with get_session() as session:
            onb_session = await onb_repo.get_for_update(session, session_id)
            if not onb_session:
                return None

            # Already created — idempotent
            if onb_session.club_id:
                return onb_session.club_id

            club_name = onb_session.collected_data.get("club_name")
            if not club_name:
                await onb_repo.mark_failed(session, session_id, "No club name collected.")
                return None

            user_id = onb_session.user_id

            # Ensure manager exists
            manager = await get_manager_by_discord_id(session, guild_id, user_id)
            if not manager:
                manager = await create_manager(session, guild_id, user_id)
                await session.flush()

            # Create club (validates name uniqueness)
            try:
                club = await ClubService.create_club_no_commit(
                    name=club_name,
                    guild_id=guild_id,
                    manager_id=manager.id,
                    session=session,
                )
                await session.flush()
            except ClubNameTakenError as e:
                # Name was taken between validation and completion → send back to name step
                await onb_repo.return_to_step(session, session_id, OnboardingStep.COLLECT_CLUB_NAME, str(e))
                return None

            # Persist club_id on session atomically
            await onb_repo.set_club_id(session, session_id, club.id)

            # Link club to manager
            manager.club_id = club.id

            logger.info(
                f"ensure_club_created: guild={guild_id}, user={user_id}, club={club.id}"
            )
            return club.id

    @staticmethod
    async def _deferred_archive(bot: discord.Client, session, delay_seconds: int = 12) -> None:
        """Wait delay_seconds then archive the onboarding thread."""
        import asyncio
        await asyncio.sleep(delay_seconds)
        try:
            await renderers.archive_thread(
                bot,
                session.thread_id,
                delete_starter_message_id=session.starter_message_id,
            )
        except Exception as e:
            logger.warning(f"_deferred_archive: failed for session {session.id}: {e}")
