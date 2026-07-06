# packages/player_engine/player_engine/generated_player.py
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeneratedPlayer:
    """Procedurally generated squad player (not a Discord/DB entity)."""

    guild_id: str
    club_id: uuid.UUID | None
    first_name: str
    last_name: str
    display_name: str
    position: str
    age: int
    overall: int
    potential: int
    value: int
    wage: int
    fitness: int = 100
    sharpness: int = 50
    morale: int = 75
    preferred_foot: str = "Right"
    weak_foot: int = 3
    skill_moves: int = 3
    traits: dict[str, Any] = field(default_factory=dict)
    is_retired: bool = False
    nationality: str = "British"
