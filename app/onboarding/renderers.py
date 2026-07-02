"""
Onboarding renderers — responsible for fetching threads and delivering step messages.
All functions accept a bot instance plus a session or thread_id.
They log errors and swallow Discord API failures gracefully so they never crash
the caller's async context.
"""
import logging
import discord
from app.ui.components import V2View
from app.onboarding import views as step_views
from app.onboarding import embeds

logger = logging.getLogger("app.onboarding.renderers")

IS_COMPONENTS_V2 = 32768  # discord IS_COMPONENTS_V2 flag value (1 << 15)


async def _get_thread(bot: discord.Client, thread_id: str | int | None) -> discord.Thread | None:
    """Fetch a Discord Thread object by ID, returning None on failure."""
    if not thread_id:
        return None
    try:
        channel = bot.get_channel(int(thread_id))
        if isinstance(channel, discord.Thread):
            return channel
        # Not in cache — try fetching from API
        channel = await bot.fetch_channel(int(thread_id))
        if isinstance(channel, discord.Thread):
            return channel
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        logger.warning(f"Could not fetch thread {thread_id}: {e}")
    return None


async def send_current_step(
    bot: discord.Client,
    thread_id: str | int,
    session,  # OnboardingSession
) -> None:
    """Send the Components V2 message for the session's current step into the thread."""
    thread = await _get_thread(bot, thread_id)
    if thread is None:
        logger.warning(f"send_current_step: thread {thread_id} not found")
        return
    view = step_views.step_view(session)
    if view is None:
        logger.warning(f"send_current_step: no view for step {session.current_step}")
        return
    try:
        await thread.send(view=view)
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.error(f"send_current_step: failed to send to thread {thread_id}: {e}")


async def send_success(
    bot: discord.Client,
    session,  # OnboardingSession
    club_name: str,
    players: list = None,
) -> None:
    """Send the completion success message to the session's thread."""
    thread = await _get_thread(bot, session.thread_id)
    if thread is None:
        return
    view = step_views.success_view(club_name, players=players)
    try:
        await thread.send(view=view)
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.error(f"send_success: failed for thread {session.thread_id}: {e}")


async def send_name_taken_retry(
    bot: discord.Client,
    session,  # OnboardingSession
    taken_name: str,
) -> None:
    """Send an error+retry message when the chosen club name is already taken."""
    thread = await _get_thread(bot, session.thread_id)
    if thread is None:
        return
    view = step_views.name_taken_retry_view(session.id, taken_name)
    try:
        await thread.send(view=view)
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.error(f"send_name_taken_retry: failed for thread {session.thread_id}: {e}")


async def send_nudge(
    bot: discord.Client,
    session,  # OnboardingSession
) -> None:
    """Send the inactivity nudge to the session thread."""
    thread = await _get_thread(bot, session.thread_id)
    if thread is None:
        return
    view = step_views.nudge_view(session.id, session.current_step)
    try:
        await thread.send(view=view)
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.error(f"send_nudge: failed for thread {session.thread_id}: {e}")



async def archive_thread(
    bot: discord.Client,
    thread_id: str | int,
    delete_starter_message_id: str | int | None = None,
) -> None:
    """
    Archive (and optionally delete the starter message for) the onboarding thread.
    For public threads the starter message is a real channel message; for private
    threads there is no starter message.
    """
    thread = await _get_thread(bot, thread_id)
    if thread is None:
        return
    try:
        if delete_starter_message_id:
            # Starter message lives in the parent channel
            parent = thread.parent
            if parent:
                try:
                    starter_msg = await parent.fetch_message(int(delete_starter_message_id))
                    await starter_msg.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass  # Already deleted or gone
        await thread.edit(archived=True)
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.warning(f"archive_thread: could not archive thread {thread_id}: {e}")
        raise  # Let the sweeper record the error
