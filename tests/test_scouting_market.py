from economy import scouting_purchase_price, GameConfig


def test_scouting_purchase_premium() -> None:
    cfg = GameConfig()
    buy = scouting_purchase_price(70, "Rare", cfg, age=18, potential=85)
    assert buy >= 100
