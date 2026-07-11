# tests/test_bot_match_squad.py
from __future__ import annotations

import random
import re

from match_engine import build_bot_match_squad

_STUB = re.compile(r"^Opponent (Striker|Midfielder|Defender)$")


def test_build_bot_match_squad_shape_and_names() -> None:
    squad = build_bot_match_squad(78, random.Random(42))
    assert len(squad) == 11
    names = [p.name for p in squad]
    assert len(set(names)) == 11
    assert all(not _STUB.match(n) for n in names)
    positions = {p.position for p in squad}
    assert {"GK", "DEF", "MID", "FWD"} <= positions
    for p in squad:
        assert abs(p.overall - 78) <= 2
        for attr in (p.pac, p.sho, p.pas, p.dri, p.def_stat, p.phy):
            assert abs(attr - p.overall) <= 3


def test_build_bot_match_squad_deterministic() -> None:
    a = build_bot_match_squad(84, random.Random(99))
    b = build_bot_match_squad(84, random.Random(99))
    assert [p.name for p in a] == [p.name for p in b]
    assert [p.overall for p in a] == [p.overall for p in b]
