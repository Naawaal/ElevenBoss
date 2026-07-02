"""
Tests for OnboardingService — mocked DB and Discord layers.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.onboarding_service import OnboardingService
from app.services.club_service import ClubNameTakenError
from app.onboarding.steps import OnboardingStep


def make_interaction(guild_id=12345, user_id=99999):
    interaction = MagicMock()
    interaction.guild_id = guild_id
    interaction.user.id = user_id
    interaction.user.display_name = "TestManager"
    interaction.user.mention = f"<@{user_id}>"
    interaction.channel_id = 55555
    interaction.channel = MagicMock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.client = MagicMock()
    return interaction


def make_session():
    return AsyncMock()


# ── start_or_resume_registration ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_existing_club_sends_error():
    interaction = make_interaction()
    fake_club = MagicMock()
    fake_club.name = "Arsenal FC"

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.ClubService.get_user_club", new_callable=AsyncMock, return_value=fake_club),
    ):
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=MagicMock())
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_gs.return_value = ctx

        await OnboardingService.start_or_resume_registration(interaction)

    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "already manage" in msg.lower() or "Arsenal FC" in msg


@pytest.mark.asyncio
async def test_register_redirects_to_existing_active_session():
    """If an active session exists with a valid thread, user is redirected."""
    interaction = make_interaction()
    fake_session = MagicMock()
    fake_session.thread_id = "777777"
    fake_session.id = uuid.uuid4()
    fake_session.status = "ACTIVE"

    fake_thread = MagicMock(spec=["mention", "archived", "__class__"])
    fake_thread.archived = False
    # Make the thread appear as a discord.Thread instance
    import discord
    fake_thread.__class__ = discord.Thread
    fake_thread.mention = "<#777777>"

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.ClubService.get_user_club", new_callable=AsyncMock, return_value=None),
        patch("app.services.onboarding_service.onb_repo.get_active_session", new_callable=AsyncMock, return_value=fake_session),
        patch("app.services.onboarding_service.get_or_create_guild_config", new_callable=AsyncMock),
    ):
        mock_db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        interaction.client.get_channel = MagicMock(return_value=fake_thread)

        await OnboardingService.start_or_resume_registration(interaction)

    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "active setup session" in msg.lower() or "continue" in msg.lower()


# ── handle_club_name_modal ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_club_name_modal_invalid_name_stays_on_step():
    """An invalid name should keep the session on COLLECT_CLUB_NAME."""
    interaction = make_interaction()
    session_id = uuid.uuid4()

    fake_onb = MagicMock()
    fake_onb.id = session_id
    fake_onb.user_id = str(interaction.user.id)
    fake_onb.current_step = OnboardingStep.COLLECT_CLUB_NAME
    fake_onb.thread_id = "12345"
    fake_onb.collected_data = {}

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.onb_repo.get_for_update", new_callable=AsyncMock, return_value=fake_onb),
        patch("app.services.onboarding_service.renderers.send_current_step", new_callable=AsyncMock),
    ):
        mock_db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        # "@" characters are invalid → ClubNameError
        await OnboardingService.handle_club_name_modal(
            interaction=interaction,
            session_id=session_id,
            raw_name="@everyone",
        )

    # Should not advance step
    interaction.response.defer.assert_awaited()


@pytest.mark.asyncio
async def test_handle_club_name_modal_valid_name_advances_step():
    """A valid, unique name should advance the session to EXPLAIN_NEXT_STEPS."""
    interaction = make_interaction()
    session_id = uuid.uuid4()

    fake_onb = MagicMock()
    fake_onb.id = session_id
    fake_onb.user_id = str(interaction.user.id)
    fake_onb.current_step = OnboardingStep.COLLECT_CLUB_NAME
    fake_onb.thread_id = "12345"
    fake_onb.collected_data = {}

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.onb_repo.get_for_update", new_callable=AsyncMock, return_value=fake_onb),
        patch("app.services.onboarding_service.ClubService.club_name_exists", new_callable=AsyncMock, return_value=False),
        patch("app.services.onboarding_service.onb_repo.save_collected_data", new_callable=AsyncMock),
        patch("app.services.onboarding_service.onb_repo.advance_step", new_callable=AsyncMock),
        patch("app.services.onboarding_service.renderers.send_current_step", new_callable=AsyncMock),
    ):
        mock_db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await OnboardingService.handle_club_name_modal(
            interaction=interaction,
            session_id=session_id,
            raw_name="Arsenal FC",
        )

    interaction.response.defer.assert_awaited()


@pytest.mark.asyncio
async def test_handle_club_name_modal_taken_name_shows_retry():
    """A name already taken should send the retry screen without advancing."""
    interaction = make_interaction()
    session_id = uuid.uuid4()

    fake_onb = MagicMock()
    fake_onb.id = session_id
    fake_onb.user_id = str(interaction.user.id)
    fake_onb.current_step = OnboardingStep.COLLECT_CLUB_NAME
    fake_onb.thread_id = "12345"
    fake_onb.collected_data = {}

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.onb_repo.get_for_update", new_callable=AsyncMock, return_value=fake_onb),
        patch("app.services.onboarding_service.ClubService.club_name_exists", new_callable=AsyncMock, return_value=True),
        patch("app.services.onboarding_service.renderers.send_name_taken_retry", new_callable=AsyncMock) as mock_retry,
    ):
        mock_db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await OnboardingService.handle_club_name_modal(
            interaction=interaction,
            session_id=session_id,
            raw_name="Arsenal FC",
        )

    mock_retry.assert_awaited_once()


# ── Ownership guard ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_next_step_rejects_wrong_user():
    """A user who doesn't own the session should receive an error."""
    interaction = make_interaction(user_id=11111)
    session_id = uuid.uuid4()

    fake_onb = MagicMock()
    fake_onb.id = session_id
    fake_onb.user_id = "99999"  # different user
    fake_onb.current_step = OnboardingStep.WELCOME

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.onb_repo.get_for_update", new_callable=AsyncMock, return_value=fake_onb),
    ):
        mock_db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await OnboardingService.handle_next_step(
            interaction=interaction,
            session_id=session_id,
            current_step=OnboardingStep.WELCOME,
        )

    interaction.followup.send.assert_awaited()
    msg = interaction.followup.send.call_args[0][0]
    assert "belong" in msg.lower() or "own" in msg.lower()


@pytest.mark.asyncio
async def test_cleanup_old_threads_and_sessions():
    """Verify that cleanup_old_threads_and_sessions archives previous sessions and thread fallbacks."""
    interaction = make_interaction()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()


    # Fake old session
    old_session = MagicMock()
    old_session.thread_id = "111111"
    old_session.starter_message_id = "222222"
    old_session.status = "FAILED"

    # Fake query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [old_session]
    mock_db.execute.return_value = mock_result

    # Mock active_threads list on guild
    fake_thread = MagicMock()
    fake_thread.name = f"⚽ Registration — {interaction.user.display_name}"
    fake_thread.id = 333333
    fake_thread.edit = AsyncMock()
    interaction.guild.active_threads = AsyncMock(return_value=[fake_thread])

    with patch("app.services.onboarding_service.renderers.archive_thread", new_callable=AsyncMock) as mock_archive:
        await OnboardingService.cleanup_old_threads_and_sessions(
            interaction=interaction,
            db_session=mock_db,
            active_session_id=None,
        )

        # Should archive the DB session's thread
        mock_archive.assert_awaited_once_with(
            interaction.client,
            "111111",
            delete_starter_message_id="222222",
        )
        
        # Should mark DB session as abandoned
        assert old_session.status == "ABANDONED"
        assert old_session.cleanup_after is not None

        # Should scan guild and edit/archive the matching thread
        fake_thread.edit.assert_awaited_once_with(archived=True)


@pytest.mark.asyncio
async def test_handle_finish_updates_loading_and_completes():
    """Verify that handle_finish immediately defers, edits response to loading card, and calls complete_registration."""
    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.guild_id = 99999
    interaction.response = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.client = MagicMock()

    session_id = uuid.uuid4()
    fake_onb = MagicMock()
    fake_onb.id = session_id
    fake_onb.user_id = "12345"
    fake_onb.collected_data = {"club_name": "Test FC"}
    fake_onb.current_step = OnboardingStep.RECRUIT_PLAYERS

    mock_complete = AsyncMock()

    with (
        patch("app.services.onboarding_service.get_session") as mock_gs,
        patch("app.services.onboarding_service.onb_repo.get_for_update", new_callable=AsyncMock, return_value=fake_onb),
        patch("app.services.onboarding_service.OnboardingService.complete_registration", mock_complete),
    ):
        mock_db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await OnboardingService.handle_finish(
            interaction=interaction,
            session_id=session_id,
        )

    # 1. Should defer immediately
    interaction.response.defer.assert_awaited_once()

    # 2. Should update original message to loading view
    interaction.edit_original_response.assert_awaited_once()
    loading_view = interaction.edit_original_response.call_args[1]["view"]
    assert loading_view is not None

    # 3. Should advance session to COMPLETE
    assert fake_onb.current_step == OnboardingStep.COMPLETE

    # 4. Should call complete_registration with interaction passed
    mock_complete.assert_awaited_once_with(
        bot=interaction.client,
        session_id=session_id,
        guild_id=99999,
        interaction=interaction,
    )



