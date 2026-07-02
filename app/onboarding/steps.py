"""
Onboarding step definitions for the V1 guided /register flow.
"""
from enum import Enum


class OnboardingStep(str, Enum):
    WELCOME = "WELCOME"
    EXPLAIN_CLUBS = "EXPLAIN_CLUBS"
    COLLECT_CLUB_NAME = "COLLECT_CLUB_NAME"
    RECRUIT_PLAYERS = "RECRUIT_PLAYERS"
    COMPLETE = "COMPLETE"


# Ordered sequence of steps the user walks through
STEP_ORDER_V1: list[OnboardingStep] = [
    OnboardingStep.WELCOME,
    OnboardingStep.EXPLAIN_CLUBS,
    OnboardingStep.COLLECT_CLUB_NAME,
    OnboardingStep.RECRUIT_PLAYERS,
    OnboardingStep.COMPLETE,
]

# Steps that are rendered to the user (COMPLETE is internal)
VISIBLE_STEPS: list[OnboardingStep] = [
    s for s in STEP_ORDER_V1 if s != OnboardingStep.COMPLETE
]


def next_step(current: str) -> OnboardingStep | None:
    """Return the step that follows `current`, or None if current is the last step."""
    try:
        idx = STEP_ORDER_V1.index(OnboardingStep(current))
    except ValueError:
        return None
    if idx + 1 < len(STEP_ORDER_V1):
        return STEP_ORDER_V1[idx + 1]
    return None


def step_number(step: str) -> int:
    """Return 1-indexed position of the step within VISIBLE_STEPS, or 0 if not found."""
    try:
        return VISIBLE_STEPS.index(OnboardingStep(step)) + 1
    except ValueError:
        return 0


def total_visible_steps() -> int:
    return len(VISIBLE_STEPS)
