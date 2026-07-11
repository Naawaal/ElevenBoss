from economy.facility_effects import (
    facility_upgrade_cost,
    training_ground_drill_xp_bonus,
    youth_academy_tier,
)
from player_engine import generate_youth_intake_cards


def test_training_ground_bonus() -> None:
    assert training_ground_drill_xp_bonus(1) == 0
    assert training_ground_drill_xp_bonus(5) == 4


def test_facility_upgrade_costs() -> None:
    assert facility_upgrade_cost(1) == 750
    assert facility_upgrade_cost(4) == 12000
    assert facility_upgrade_cost(5) is None


def test_youth_academy_tier_l5() -> None:
    tier = youth_academy_tier(5)
    assert tier.pot_max == 94
    assert tier.gem_chance == 0.20


def test_generate_youth_intake_l5_bounds() -> None:
    cards = generate_youth_intake_cards(
        3,
        academy_level=5,
        first_names=["Alex"],
        last_names=["Smith"],
    )
    for card in cards:
        assert 56 <= card.overall <= 69
        assert card.potential <= 94
        assert card.role
