import logging
import uuid
import discord
from datetime import datetime, timezone

from app.db.session import get_session
from app.ui.handlers.session import ui_session_manager, UiSession
from app.models.club import Club
from app.repositories.club_repository import get_user_club
from app.services.friendly_service import FriendlyService, FriendlyMatchReport
from app.services.friendly_live_playback_service import friendly_playback_service
from app.ui.layouts.friendly_live import (
    build_friendly_invite_layout,
    build_friendly_practice_layout,
    build_live_kickoff_layout,
)
from app.ui.components import V2View, container, text_display

logger = logging.getLogger("app.ui.handlers.friendly_handler")

async def handle_friendly_challenge(
    guild_id: int,
    challenger_user: discord.Member,
    opponent_member: discord.Member
) -> V2View:
    """
    Creates a friendly challenge invitation card.
    Only the opponent can interact (Accept/Decline).
    """
    if challenger_user.id == opponent_member.id:
        raise ValueError("You cannot challenge yourself. Use `/friendly practice` to practice against bots.")
        
    if opponent_member.bot:
        raise ValueError("You cannot challenge a Discord bot user.")

    # Check challenger cooldown against this opponent
    expiry = FriendlyService.get_cooldown_expiry(challenger_user.id, opponent_member.id)
    if expiry:
        secs = int((expiry - datetime.now(timezone.utc)).total_seconds())
        mins = secs // 60
        secs_rem = secs % 60
        time_str = f"{mins}m {secs_rem}s" if mins > 0 else f"{secs}s"
        raise ValueError(f"You are on challenge cooldown against this opponent. Please wait {time_str}.")

    async with get_session() as session:
        # Fetch challenger club
        challenger_club = await get_user_club(session, guild_id, challenger_user.id)
        if not challenger_club:
            raise ValueError("You must register a club first before challenging others.")

        # Fetch opponent club
        opponent_club = await get_user_club(session, guild_id, opponent_member.id)
        if not opponent_club:
            raise ValueError(f"Opponent {opponent_member.display_name} does not have a registered club in this server.")

        # Verify clubs are in same guild
        if challenger_club.guild_id != opponent_club.guild_id:
            raise ValueError("Both clubs must be in the same server to play a friendly match.")

        # Create challenge session owned by the OPPONENT so only they can accept/decline
        ui_session = ui_session_manager.create_session(
            discord_user_id=opponent_member.id,
            guild_id=guild_id,
            metadata={
                "type": "friendly_challenge",
                "status": "pending",
                "challenger_user_id": challenger_user.id,
                "opponent_user_id": opponent_member.id,
                "challenger_club_id": str(challenger_club.id),
                "opponent_club_id": str(opponent_club.id),
                "challenger_club_name": challenger_club.name,
                "opponent_club_name": opponent_club.name
            }
        )
        # Set challenge expiry to 2 minutes
        ui_session.refresh(duration_minutes=2)
        nonce = ui_session.session_id
        
        # Set cooldown
        FriendlyService.set_cooldown(challenger_user.id, opponent_member.id, duration_minutes=5)
        
        logger.info(f"friendly_challenge_created: challenger={challenger_club.name}, opponent={opponent_club.name}, session={nonce}")
        expires_timestamp = int(ui_session.expires_at.replace(tzinfo=timezone.utc).timestamp())
        return build_friendly_invite_layout(challenger_club.name, opponent_club.name, opponent_member.mention, nonce, expires_timestamp)

async def handle_friendly_accept(
    session_id: str,
    user_id: int,
    nonce: str,
    interaction: discord.Interaction = None
) -> V2View:
    """
    Simulates the friendly match, transitions to playing state,
    and kicks off the progressive live match playback background loop.
    """
    session_obj = ui_session_manager.get_session(nonce)
    if not session_obj or session_obj.metadata.get("type") != "friendly_challenge":
        raise ValueError("This challenge has expired (challenges only last 2 minutes).")
        
    opponent_id = session_obj.metadata.get("opponent_user_id")
    challenger_id = session_obj.metadata.get("challenger_user_id")
    
    if user_id == challenger_id:
        raise ValueError("Only the challenged manager can accept/decline this challenge. You can cancel it using the Cancel button.")
    if user_id != opponent_id:
        raise ValueError("You are not a participant in this friendly challenge.")

    status = session_obj.metadata.get("status")
    if status == "playing" or status == "simulating":
        raise ValueError("This match simulation is already in progress.")
    if status == "completed":
        raise ValueError("This friendly challenge has already been simulated.")
    if status == "declined":
        raise ValueError("This friendly challenge was declined.")
    if status != "pending":
        raise ValueError("This challenge session is not pending.")

    # Lock status to simulating to prevent double clicks during the sync phase
    session_obj.metadata["status"] = "simulating"

    try:
        challenger_club_id = uuid.UUID(session_obj.metadata["challenger_club_id"])
        opponent_club_id = uuid.UUID(session_obj.metadata["opponent_club_id"])
        guild_id = session_obj.guild_id

        async with get_session() as session:
            # Load clubs from DB
            from sqlalchemy.future import select
            res1 = await session.execute(select(Club).where(Club.id == challenger_club_id))
            challenger_club = res1.scalar_one_or_none()
            res2 = await session.execute(select(Club).where(Club.id == opponent_club_id))
            opponent_club = res2.scalar_one_or_none()

            if not challenger_club or not opponent_club:
                raise ValueError("One of the clubs in this challenge was deleted.")

            # Resolve lineups in-memory (with fallbacks if needed)
            home_formation, home_starters = await FriendlyService.resolve_team_lineup(session, guild_id, challenger_club)
            away_formation, away_starters = await FriendlyService.resolve_team_lineup(session, guild_id, opponent_club)

        # Assemble engine inputs
        from app.engine.match_engine import MatchTeamInput
        home_input = MatchTeamInput(
            club_id=str(challenger_club.id),
            club_name=challenger_club.name,
            formation=home_formation,
            players=home_starters,
            is_home=True
        )
        away_input = MatchTeamInput(
            club_id=str(opponent_club.id),
            club_name=opponent_club.name,
            formation=away_formation,
            players=away_starters,
            is_home=False
        )

        # Generate a seed and run match simulation
        import secrets
        seed = secrets.randbits(32)
        report = FriendlyService.simulate_friendly(home_input, away_input, seed)

        # Store report in-memory on the session object
        session_obj.metadata["report"] = report
        session_obj.metadata["status"] = "playing"
        session_obj.refresh(duration_minutes=10)

        # Start progressive live playback in background if interaction is provided
        if interaction:
            friendly_playback_service.start_playback(nonce, report, interaction)
        
        logger.info(f"friendly_challenge_accepted: session={nonce}, kicking off live playback")
        return build_live_kickoff_layout(report.home_club_name, report.away_club_name, nonce)
        
    except Exception as e:
        # Revert status on failure so it can be retried if it was a transient error
        session_obj.metadata["status"] = "pending"
        raise e

async def handle_friendly_decline(
    session_id: str,
    user_id: int,
    nonce: str
) -> V2View:
    """
    Declines the challenge invitation.
    """
    session_obj = ui_session_manager.get_session(nonce)
    if not session_obj or session_obj.metadata.get("type") != "friendly_challenge":
        raise ValueError("This challenge has expired (challenges only last 2 minutes).")
        
    opponent_id = session_obj.metadata.get("opponent_user_id")
    challenger_id = session_obj.metadata.get("challenger_user_id")
    
    if user_id == challenger_id:
        raise ValueError("Only the challenged manager can accept/decline this challenge. You can cancel it using the Cancel button.")
    if user_id != opponent_id:
        raise ValueError("You are not a participant in this friendly challenge.")

    status = session_obj.metadata.get("status")
    if status != "pending":
        raise ValueError("This challenge session is not pending.")

    # Update status to declined
    session_obj.metadata["status"] = "declined"
    
    # Remove session
    ui_session_manager._sessions.pop(nonce, None)
    
    logger.info(f"friendly_challenge_declined: session={nonce}")
    comp_payload = [
        container([
            text_display(f"❌ *Challenge declined by {session_obj.metadata.get('opponent_club_name') or 'opponent'}.*")
        ])
    ]
    return V2View(comp_payload)

async def handle_friendly_cancel(
    session_id: str,
    user_id: int,
    nonce: str
) -> V2View:
    """
    Cancels the friendly challenge. Only the challenger can cancel it.
    """
    session_obj = ui_session_manager.get_session(nonce)
    if not session_obj or session_obj.metadata.get("type") != "friendly_challenge":
        raise ValueError("This challenge has expired (challenges only last 2 minutes).")

    challenger_id = session_obj.metadata.get("challenger_user_id")
    if user_id != challenger_id:
        raise ValueError("Only the challenger who sent the challenge can cancel it.")

    status = session_obj.metadata.get("status")
    if status != "pending":
        raise ValueError("This challenge session is not pending.")

    # Update status and remove session
    session_obj.metadata["status"] = "cancelled"
    ui_session_manager._sessions.pop(nonce, None)

    logger.info(f"friendly_challenge_cancelled: session={nonce}")
    comp_payload = [
        container([
            text_display(f"🗑️ *Challenge cancelled by the challenger ({session_obj.metadata.get('challenger_club_name') or 'challenger'}).*")
        ])
    ]
    return V2View(comp_payload)

async def handle_friendly_skip(
    session_id: str,
    user_id: int,
    nonce: str,
    interaction: discord.Interaction = None
) -> V2View:
    """
    Handles immediate skip to full-time report.
    Cancels playback loop and displays final stats/score card.
    """
    # We validate nonce session, but allow either participant to call skip (unlike standard validation which checks only session owner)
    session_obj = ui_session_manager.get_session(nonce)
    if not session_obj:
        raise ValueError("This friendly match session has expired or is invalid.")

    # Check permission: must be challenger or opponent (or session owner for practice mode)
    if session_obj.metadata.get("type") == "friendly_practice":
        if user_id != session_obj.discord_user_id:
            raise ValueError("You do not have permission to skip this practice match.")
    else:
        challenger_id = int(session_obj.metadata["challenger_user_id"])
        opponent_id = int(session_obj.metadata["opponent_user_id"])
        if user_id not in (challenger_id, opponent_id):
            raise ValueError("Only the challenger or opponent can skip this friendly match.")

    report = session_obj.metadata.get("report")
    if not report:
        raise ValueError("No match report was found for this session.")

    logger.info(f"friendly_match_skip: session={nonce}, requested_by={user_id}")
    view = await friendly_playback_service.skip_to_full_time(nonce, report, interaction)
    return view

async def handle_friendly_practice(
    guild_id: int,
    user: discord.Member
) -> V2View:
    """
    Renders the practice AI difficulty selection console.
    """
    async with get_session() as session:
        club = await get_user_club(session, guild_id, user.id)
        if not club:
            raise ValueError("You must register a club first before playing practice matches.")

        # Create practice session owned by the manager
        ui_session = ui_session_manager.create_session(
            discord_user_id=user.id,
            guild_id=guild_id,
            metadata={
                "type": "friendly_practice",
                "status": "pending",
                "club_id": str(club.id),
                "club_name": club.name
            }
        )
        nonce = ui_session.session_id
        
        logger.info(f"friendly_practice_hub_opened: user_id={user.id}, session={nonce}")
        return build_friendly_practice_layout(nonce)

async def handle_friendly_practice_select(
    selected_difficulty: str,
    user_id: int,
    nonce: str,
    interaction: discord.Interaction = None
) -> V2View:
    """
    Runs an instant practice match against a bot difficulty.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user_id)
    if not valid:
        raise ValueError(err_msg)
        
    session_obj = ui_session_manager.get_session(nonce)
    if not session_obj or session_obj.metadata.get("type") != "friendly_practice":
        raise ValueError("Invalid practice session.")

    status = session_obj.metadata.get("status")
    if status == "playing" or status == "simulating":
        raise ValueError("Simulation in progress.")
    if status == "completed":
        raise ValueError("This practice match is completed. Run `/friendly practice` to play another.")

    session_obj.metadata["status"] = "simulating"

    try:
        club_id = uuid.UUID(session_obj.metadata["club_id"])
        guild_id = session_obj.guild_id

        async with get_session() as session:
            # Fetch club
            from sqlalchemy.future import select
            res = await session.execute(select(Club).where(Club.id == club_id))
            club = res.scalar_one_or_none()
            if not club:
                raise ValueError("Your club was not found.")

            # Resolve lineup
            home_formation, home_starters = await FriendlyService.resolve_team_lineup(session, guild_id, club)

        # Generate transient bot team based on difficulty
        import secrets
        seed = secrets.randbits(32)
        bot_club_name = f"{selected_difficulty.title()} Bot FC"
        bot_team_input = FriendlyService.generate_transient_bot_team(selected_difficulty, bot_club_name, seed ^ 0xFAF)

        from app.engine.match_engine import MatchTeamInput
        home_input = MatchTeamInput(
            club_id=str(club.id),
            club_name=club.name,
            formation=home_formation,
            players=home_starters,
            is_home=True
        )

        # Simulate friendly
        report = FriendlyService.simulate_friendly(home_input, bot_team_input, seed)

        session_obj.metadata["report"] = report
        session_obj.metadata["status"] = "playing"
        session_obj.refresh(duration_minutes=10)

        # Start progressive live playback in background if interaction is provided
        if interaction:
            friendly_playback_service.start_playback(nonce, report, interaction)

        logger.info(f"friendly_practice_accepted: user_id={user_id}, difficulty={selected_difficulty}, starting live playback")
        return build_live_kickoff_layout(report.home_club_name, report.away_club_name, nonce)
        
    except Exception as e:
        session_obj.metadata["status"] = "pending"
        raise e
