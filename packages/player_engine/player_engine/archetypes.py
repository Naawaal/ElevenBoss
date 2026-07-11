# packages/player_engine/player_engine/archetypes.py
"""Positional player archetypes for procedural card creation."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ArchetypeDef:
    name: str
    position: str
    weights: dict[str, float]
    roll_weight: int


# Creation distributions (research R2). True OVR still uses engine.POSITION_WEIGHTS.
ARCHETYPES: dict[str, tuple[ArchetypeDef, ...]] = {
    "FWD": (
        ArchetypeDef(
            "Poacher",
            "FWD",
            {"pac": 0.10, "sho": 0.40, "pas": 0.10, "dri": 0.15, "def": 0.05, "phy": 0.20},
            30,
        ),
        ArchetypeDef(
            "Speedster",
            "FWD",
            {"pac": 0.35, "sho": 0.15, "pas": 0.10, "dri": 0.30, "def": 0.05, "phy": 0.05},
            30,
        ),
        ArchetypeDef(
            "Complete Forward",
            "FWD",
            {"pac": 0.20, "sho": 0.35, "pas": 0.10, "dri": 0.20, "def": 0.05, "phy": 0.10},
            40,
        ),
    ),
    "MID": (
        ArchetypeDef(
            "Playmaker",
            "MID",
            {"pac": 0.10, "sho": 0.15, "pas": 0.35, "dri": 0.25, "def": 0.05, "phy": 0.10},
            30,
        ),
        ArchetypeDef(
            "Destroyer",
            "MID",
            {"pac": 0.10, "sho": 0.10, "pas": 0.15, "dri": 0.10, "def": 0.30, "phy": 0.25},
            30,
        ),
        ArchetypeDef(
            "Box-to-Box",
            "MID",
            {"pac": 0.15, "sho": 0.15, "pas": 0.20, "dri": 0.15, "def": 0.15, "phy": 0.20},
            40,
        ),
    ),
    "DEF": (
        ArchetypeDef(
            "Stopper",
            "DEF",
            {"pac": 0.10, "sho": 0.02, "pas": 0.10, "dri": 0.03, "def": 0.45, "phy": 0.30},
            30,
        ),
        ArchetypeDef(
            "Wing-Back",
            "DEF",
            {"pac": 0.25, "sho": 0.03, "pas": 0.20, "dri": 0.15, "def": 0.25, "phy": 0.12},
            30,
        ),
        ArchetypeDef(
            "Ball-Playing Defender",
            "DEF",
            {"pac": 0.10, "sho": 0.03, "pas": 0.25, "dri": 0.07, "def": 0.35, "phy": 0.20},
            40,
        ),
    ),
    "GK": (
        ArchetypeDef(
            "Shot Stopper",
            "GK",
            {"pac": 0.10, "sho": 0.00, "pas": 0.10, "dri": 0.00, "def": 0.55, "phy": 0.25},
            30,
        ),
        ArchetypeDef(
            "Sweeper Keeper",
            "GK",
            {"pac": 0.25, "sho": 0.00, "pas": 0.20, "dri": 0.00, "def": 0.40, "phy": 0.15},
            30,
        ),
        ArchetypeDef(
            "Classic Keeper",
            "GK",
            {"pac": 0.15, "sho": 0.00, "pas": 0.15, "dri": 0.00, "def": 0.50, "phy": 0.20},
            40,
        ),
    ),
}


def archetypes_for(position: str) -> tuple[ArchetypeDef, ...]:
    return ARCHETYPES.get(position, ARCHETYPES["MID"])


def roll_archetype(position: str, rng: random.Random | None = None) -> ArchetypeDef:
    r = rng or random
    options = archetypes_for(position)
    weights = [a.roll_weight for a in options]
    return r.choices(list(options), weights=weights, k=1)[0]
