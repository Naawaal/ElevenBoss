import pytest
from app.engine.bot_club_generator import generate_bot_clubs_data, GeneratedBotClub

def test_generate_bot_clubs_data():
    count = 5
    existing = {"Ironvale FC"}
    clubs = generate_bot_clubs_data("123456", count, existing)
    
    # Check count
    assert len(clubs) == count
    
    # Check uniqueness of names and short names
    names = [c.name for c in clubs]
    short_names = [c.short_name for c in clubs]
    assert len(names) == len(set(names))
    assert len(short_names) == len(set(short_names))
    
    # Check excluded names
    assert "Ironvale FC" not in names
    
    # Check attributes
    for c in clubs:
        assert isinstance(c, GeneratedBotClub)
        assert len(c.short_name) >= 2 and len(c.short_name) <= 5
        assert c.budget > 0
        assert 100 <= c.reputation <= 1000
        assert c.stadium_capacity > 0


def test_generate_bot_clubs_exhaustion_and_collisions():
    # Exhaust all templates
    from app.engine.bot_club_generator import BOT_NAME_TEMPLATES
    existing = {t[0] for t in BOT_NAME_TEMPLATES}
    
    # Also mock collision with default fallback names: Bot Club A, Bot Club B
    existing.add("Bot Club A")
    existing.add("Bot Club B")
    
    clubs = generate_bot_clubs_data("123456", 3, existing)
    
    assert len(clubs) == 3
    names = [c.name for c in clubs]
    
    # It should skip "Bot Club A" and "Bot Club B" and generate unique ones starting at "Bot Club C"
    assert "Bot Club A" not in names
    assert "Bot Club B" not in names
    assert "Bot Club C" in names
    assert "Bot Club D" in names
    assert "Bot Club E" in names

