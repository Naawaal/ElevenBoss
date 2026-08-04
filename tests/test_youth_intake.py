from player_engine import generate_youth_intake_cards, rarity_potential_cap


def test_generate_youth_intake_cards_bounds() -> None:
    """V2: default count 2; rarity-first; ceilings; youth ages."""
    cards = generate_youth_intake_cards(
        first_names=["Alex"],
        last_names=["Smith"],
    )
    assert len(cards) == 2
    for card in cards:
        assert card.rarity in {"Common", "Rare", "Epic", "Legendary"}
        assert 16 <= card.age <= 19
        assert card.potential <= rarity_potential_cap(card.rarity)
        assert card.potential >= card.overall
        assert card.date_of_birth
        assert card.role
