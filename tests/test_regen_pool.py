from player_engine import generate_regen_from_retired


def test_generate_regen_from_retired() -> None:
    retired = {
        "id": "00000000-0000-0000-0000-000000000001",
        "position": "FWD",
        "overall": 82,
        "potential": 88,
        "base_potential": 88,
    }
    regen = generate_regen_from_retired(
        retired,
        first_names=["Alex"],
        last_names=["Smith"],
    )
    assert regen["position"] == "FWD"
    assert 55 <= regen["overall"] <= 70
    assert 16 <= regen["age"] <= 19
    assert regen["potential"] >= regen["overall"]
    assert regen["source_card_id"] == retired["id"]
