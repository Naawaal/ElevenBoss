"""
V2View factories for each onboarding step.
Each function wraps the corresponding embeds payload in a V2View instance.
"""
import uuid
from app.ui.components import V2View
from app.onboarding import embeds
from app.models.onboarding_session import OnboardingSession


def welcome_view(session_id: uuid.UUID) -> V2View:
    return V2View(embeds.build_welcome(session_id))


def explain_clubs_view(session_id: uuid.UUID) -> V2View:
    return V2View(embeds.build_explain_clubs(session_id))


def collect_club_name_view(session_id: uuid.UUID, error: str | None = None) -> V2View:
    return V2View(embeds.build_collect_club_name(session_id, error=error))


def recruit_players_view(session_id: uuid.UUID, club_name: str) -> V2View:
    return V2View(embeds.build_recruit_players(session_id, club_name))


def success_view(club_name: str, players: list = None) -> V2View:
    return V2View(embeds.build_success(club_name, players=players))


def name_taken_retry_view(session_id: uuid.UUID, taken_name: str) -> V2View:
    return V2View(embeds.build_name_taken_retry(session_id, taken_name))


def nudge_view(session_id: uuid.UUID, current_step: str) -> V2View:
    return V2View(embeds.build_nudge(session_id, current_step))


def step_view(session: OnboardingSession) -> V2View | None:
    """
    Return the appropriate V2View for the current step in a session.
    Returns None for COMPLETE or unknown steps (handled elsewhere).
    """
    sid = session.id
    step = session.current_step
    club_name = session.collected_data.get("club_name", "")

    from app.onboarding.steps import OnboardingStep
    if step == OnboardingStep.WELCOME:
        return welcome_view(sid)
    elif step == OnboardingStep.EXPLAIN_CLUBS:
        return explain_clubs_view(sid)
    elif step == OnboardingStep.COLLECT_CLUB_NAME:
        return collect_club_name_view(sid)
    elif step == OnboardingStep.RECRUIT_PLAYERS:
        return recruit_players_view(sid, club_name)
    return None
