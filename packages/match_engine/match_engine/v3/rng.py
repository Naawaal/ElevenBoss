# packages/match_engine/match_engine/v3/rng.py
"""Seeded RNG factory — never use module-global random for sporting outcomes."""
from __future__ import annotations

import random


def make_match_rng(seed: int) -> random.Random:
    return random.Random(int(seed))
