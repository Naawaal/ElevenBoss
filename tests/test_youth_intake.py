from player_engine import generate_youth_intake_cards


def test_generate_youth_intake_cards_bounds() -> None:
    cards = generate_youth_intake_cards(
        3,
        first_names=["Alex"],
        last_names=["Smith"],
    )
    assert len(cards) == 3
    for card in cards:
        assert card["rarity"] == "Common"
        assert 16 <= card["age"] <= 19
        assert 50 <= card["overall"] <= 65
        assert 72 <= card["potential"] <= 82
        assert card["potential"] >= card["overall"]
        assert card["date_of_birth"]
