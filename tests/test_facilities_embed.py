from apps.discord_bot.views.store_facilities import facilities_embed


def test_facilities_embed_returns_both_facilities() -> None:
    embed = facilities_embed(
        {
            "youth_academy_level": 2,
            "training_ground_level": 3,
            "coins": 5000,
            "matches_played": 10,
        }
    )
    assert embed is not None
    assert "Club Facilities" in embed.title
    names = [f.name for f in embed.fields]
    assert any("Youth Academy" in n for n in names)
    assert any("Training Ground" in n for n in names)


def test_facilities_embed_max_level() -> None:
    embed = facilities_embed(
        {
            "youth_academy_level": 5,
            "training_ground_level": 5,
            "coins": 0,
            "matches_played": 100,
        }
    )
    body = "\n".join(f.value for f in embed.fields)
    assert "Max level" in body
