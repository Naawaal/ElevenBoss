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
