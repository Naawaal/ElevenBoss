# tests/test_match_engine.py
from __future__ import annotations
import pytest
from match_engine import render_commentary, bold_vars, CommentaryEngine


def test_render_commentary_bolding():
    """
    Verify that render_commentary bolds players and teams, and avoids double-bolding.
    """
    template = "...and {actor} has a chance to break it open for {team}!"
    
    # 1. Standard casing: string values should be bolded
    variables_1 = {"actor": "Jack Rogers", "team": "Mirai MidNight"}
    res_1 = render_commentary(template, variables_1)
    assert res_1 == "...and **Jack Rogers** has a chance to break it open for **Mirai MidNight**!"
    
    # 2. Already bolded values: should strip existing ** and avoid double bolding
    variables_2 = {"actor": "**Jack Rogers**", "team": "Mirai MidNight"}
    res_2 = render_commentary(template, variables_2)
    assert res_2 == "...and **Jack Rogers** has a chance to break it open for **Mirai MidNight**!"


def test_bold_vars_non_string_untouched():
    """
    Verify that bold_vars leaves non-string values untouched.
    """
    variables = {
        "actor": "Jack Rogers",
        "team": "Mirai MidNight",
        "minute": 45,
        "is_home": True
    }
    
    formatted = bold_vars(variables)
    assert formatted["actor"] == "**Jack Rogers**"
    assert formatted["team"] == "**Mirai MidNight**"
    assert formatted["minute"] == 45
    assert formatted["is_home"] is True


def test_commentary_engine_markdown_integration():
    """
    Verify integration in CommentaryEngine using a mock state context and tags.
    """
    engine = CommentaryEngine()
    
    # Let's verify that when we call get_commentary, the output has bolded player/team names.
    variables = {"actor": "Jack Rogers", "team": "Mirai MidNight"}
    
    # Let's sample a kickoff event
    res = engine.get_commentary("KICKOFF", [], variables)
    assert "**Mirai MidNight**" in res["text"]
    assert "****Mirai MidNight****" not in res["text"]
