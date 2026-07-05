# tests/test_engine.py
from __future__ import annotations
import pytest
from gacha import generate_starter_squad
from match_engine import simulate_match, MatchInput, MatchPlayerCard, MatchResult

def test_generate_starter_squad():
    """
    Verify the starter squad generates exactly 11 players with the correct 4-4-2 positional array:
    - 1 GK, 4 DEF, 4 MID, 2 FWD
    """
    squad = generate_starter_squad()
    
    # 1. Total players should be 11
    players = squad.all_players
    assert len(players) == 11
    
    # 2. Count positions
    positions = [p.position for p in players]
    assert positions.count("GK") == 1
    assert positions.count("DEF") == 4
    assert positions.count("MID") == 4
    assert positions.count("FWD") == 2
    
    # 3. Check rarity and rating ranges
    assert squad.marquee.rarity in ["Rare", "Epic"]
    for p in squad.youth:
        assert p.rarity == "Common"
        assert 50 <= p.base_rating <= 64

def test_match_simulator():
    """
    Verify the match simulator returns a valid MatchResult Pydantic model with expected rewards.
    """
    # 1. Create a mock starting 11 using MatchPlayerCard
    my_players = [
        MatchPlayerCard(
            name=f"Player {i}",
            position="DEF",
            overall=70,
            pac=70,
            sho=70,
            pas=70,
            dri=70,
            def_stat=70,
            phy=70,
            morale=50,
            playstyles=[]
        )
        for i in range(11)
    ]
    
    match_input = MatchInput(
        my_players=my_players,
        opponent_base_rating=72.0
    )
    
    # 2. Run simulation
    result = simulate_match(match_input)
    
    # 3. Assert result type and structure
    assert isinstance(result, MatchResult)
    assert result.result in ["win", "draw", "loss"]
    assert result.my_rating == 70.0
    assert result.opponent_rating == 72.0
    assert result.goals_for >= 0
    assert result.goals_against >= 0
    assert 20 <= result.possession_home <= 80
    assert 20 <= result.possession_away <= 80
    assert result.possession_home + result.possession_away == 100
    assert result.shots_home >= result.goals_for
    assert result.shots_away >= result.goals_against
    assert len(result.motm) > 0
    
    # 4. Verify outcomes match expectations
    if result.result == "win":
        assert result.goals_for > result.goals_against
        assert result.coins_earned == 150
        assert result.points_earned == 3
    elif result.result == "draw":
        assert result.goals_for == result.goals_against
        assert result.coins_earned == 50
        assert result.points_earned == 1
    else: # loss
        assert result.goals_for < result.goals_against
        assert result.coins_earned == 0
        assert result.points_earned == 0

def test_generate_match_script():
    """
    Verify the commentary generation logic outputs a chronological, valid list of MatchEvent models
    corresponding to the simulated score.
    """
    from match_engine import generate_match_script, EventType, MatchResult
    
    mock_result = MatchResult(
        result="win",
        goals_for=2,
        goals_against=1,
        my_rating=75.0,
        opponent_rating=72.0,
        coins_earned=150,
        points_earned=3
    )
    
    # Generate the script
    events = generate_match_script(mock_result, "Antigravity FC", "Opponent FC")
    
    # 1. Total events should be at least 5 (Kickoff + 3 middle events + Full Time)
    assert len(events) >= 5
    
    # 2. Check chronological sorting of minutes
    minutes = [ev.minute for ev in events]
    assert minutes == sorted(minutes)
    
    # 3. First event must be KICKOFF at minute 0
    assert events[0].type == EventType.KICKOFF
    assert events[0].minute == 0
    assert events[0].score_update == "0 - 0"
    
    # 4. Last event must be FULL_TIME at minute 90
    assert events[-1].type == EventType.FULL_TIME
    assert events[-1].minute == 90
    assert events[-1].score_update == "2 - 1"
    
    # 5. Count total goal events in between
    goal_events = [ev for ev in events if ev.type == EventType.GOAL]
    assert len(goal_events) == 3 # 2 home goals + 1 away goal

def test_commentary_engine_fallback() -> None:
    from match_engine import CommentaryEngine
    engine = CommentaryEngine()

    # 1. Match specific tags: "late" is matched for CHANCE
    variables = {"actor": "John Doe", "team": "FC Barcelona"}
    res_late = engine.get_commentary("CHANCE", ["late"], variables)
    assert "defensive line" in res_late["text"] or "dangerous area" in res_late["text"]
    assert res_late["urgency"] in ["routine", "build_up", "cliffhanger"]

    # 2. Fall back to generic tags when no matching tags found
    res_fallback = engine.get_commentary("CHANCE", ["unknown_tag_abc"], variables)
    assert "picks up" in res_fallback["text"]
    assert res_fallback["urgency"] == "build_up"

def test_match_state_tag_generation() -> None:
    from match_engine import MatchState

    # Early, tied, balanced state
    state = MatchState(home_rating=75.0, away_rating=72.0, minute=10, home_score=1, away_score=1, momentum=10)
    state.update_tags()
    assert "early" in state.context_tags
    assert "tied" in state.context_tags
    assert "high_momentum" not in state.context_tags

    # Late, home leading, high momentum state
    state2 = MatchState(home_rating=75.0, away_rating=72.0, minute=80, home_score=2, away_score=1, momentum=60)
    state2.update_tags()
    assert "late" in state2.context_tags
    assert "home_leading" in state2.context_tags
    assert "high_momentum" in state2.context_tags

