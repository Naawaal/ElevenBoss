# packages/player_engine/player_engine/age_manager.py
"""Player age lifecycle — pure formulas (Phase A)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class LifecyclePhase(StrEnum):
    YOUTH = "youth"
    EARLY_PRIME = "early_prime"
    LATE_PRIME = "late_prime"
    VETERAN = "veteran"
    RETIRING = "retiring"


@dataclass(frozen=True)
class LifecycleConfig:
    youth_max: int = 21
    early_prime_max: int = 26
    late_prime_max: int = 30
    veteran_max: int = 34
    retirement_warning_age: int = 35
    retirement_age: int = 36
    xp_mult_youth: float = 1.50
    xp_mult_early_prime: float = 1.20
    xp_mult_late_prime: float = 1.00
    xp_mult_veteran: float = 0.70
    xp_mult_retiring: float = 0.40


DEFAULT_LIFECYCLE = LifecycleConfig()


def age_from_dob(dob: date, *, reference: date | None = None) -> int:
    """Whole years from date of birth (365.25-day year), clamped 15–45."""
    ref = reference or date.today()
    days = (ref - dob).days
    if days < 0:
        return 15
    years = int(days / 365.25)
    return max(15, min(45, years))


def dob_from_age(age: int, *, reference: date | None = None, day_jitter: int = 0) -> date:
    """Build a DOB that yields `age` at reference date, with optional day offset."""
    ref = reference or date.today()
    age = max(15, min(45, age))
    return ref - timedelta(days=int(age * 365.25) + day_jitter)


def lifecycle_phase(age: int, cfg: LifecycleConfig | None = None) -> LifecyclePhase:
    c = cfg or DEFAULT_LIFECYCLE
    if age <= c.youth_max:
        return LifecyclePhase.YOUTH
    if age <= c.early_prime_max:
        return LifecyclePhase.EARLY_PRIME
    if age <= c.late_prime_max:
        return LifecyclePhase.LATE_PRIME
    if age <= c.veteran_max:
        return LifecyclePhase.VETERAN
    return LifecyclePhase.RETIRING


def xp_multiplier(age: int, cfg: LifecycleConfig | None = None) -> float:
    phase = lifecycle_phase(age, cfg)
    c = cfg or DEFAULT_LIFECYCLE
    return {
        LifecyclePhase.YOUTH: c.xp_mult_youth,
        LifecyclePhase.EARLY_PRIME: c.xp_mult_early_prime,
        LifecyclePhase.LATE_PRIME: c.xp_mult_late_prime,
        LifecyclePhase.VETERAN: c.xp_mult_veteran,
        LifecyclePhase.RETIRING: c.xp_mult_retiring,
    }[phase]


def apply_xp_age_multiplier(base_xp: int, age: int, cfg: LifecycleConfig | None = None) -> int:
    if base_xp <= 0:
        return 0
    mult = xp_multiplier(age, cfg)
    return max(1, int(round(base_xp * mult)))


def yearly_stat_decline(age: int, cfg: LifecycleConfig | None = None) -> dict[str, int]:
    """Per birthday-year stat deltas (negative = decline). Empty if still in prime."""
    phase = lifecycle_phase(age, cfg)
    if phase == LifecyclePhase.VETERAN:
        return {"pac": -1, "phy": -1, "pas": 0, "def": 0, "sho": 0, "dri": 0}
    if phase == LifecyclePhase.RETIRING:
        pas_def = -1 if age >= 33 else 0
        return {"pac": -2, "phy": -2, "pas": pas_def, "def": pas_def, "sho": 0, "dri": 0}
    return {}


def lifecycle_phase_label(phase: LifecyclePhase) -> str:
    return {
        LifecyclePhase.YOUTH: "Youth",
        LifecyclePhase.EARLY_PRIME: "Early Prime",
        LifecyclePhase.LATE_PRIME: "Late Prime",
        LifecyclePhase.VETERAN: "Veteran",
        LifecyclePhase.RETIRING: "Retiring",
    }[phase]


def lifecycle_phase_emoji(phase: LifecyclePhase) -> str:
    return {
        LifecyclePhase.YOUTH: "🟢",
        LifecyclePhase.EARLY_PRIME: "🔵",
        LifecyclePhase.LATE_PRIME: "⚪",
        LifecyclePhase.VETERAN: "🟡",
        LifecyclePhase.RETIRING: "🔴",
    }[phase]


def can_renew_contract(age: int, cfg: LifecycleConfig | None = None) -> bool:
    c = cfg or DEFAULT_LIFECYCLE
    return age < c.retirement_warning_age


def format_lifecycle_display(age: int | None, potential: int | None = None) -> str:
    if age is None:
        return f"📊 {potential} POT" if potential is not None else "—"
    phase = lifecycle_phase(age)
    emoji = lifecycle_phase_emoji(phase)
    label = lifecycle_phase_label(phase)
    pot_part = f" · 📊 {potential} POT" if potential is not None else ""
    return f"{age} yrs · {emoji} {label}{pot_part}"
