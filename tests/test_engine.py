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
        MatchPlayerCard(name=f"Player {i}", position="DEF", overall=70)
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
