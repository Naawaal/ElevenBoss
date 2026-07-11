# packages/gacha/gacha/generator.py
from __future__ import annotations

import json
import os
import random

from player_engine import CreatedPlayerCard, create_player_card, generate_youth_intake_cards

from .models import GachaPack, GachaPlayer, RARITY_RATING_RANGES, StarterSquad
from .pack_configs import get_pack_config

_YOUTH_POSITIONS: list[str] = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD"]
_MARQUEE_POSITIONS: list[str] = ["DEF", "DEF", "MID", "MID", "MID", "FWD"]


def _load_names() -> dict[str, list[str]]:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(dir_path, "data", "player_names.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _from_created(card: CreatedPlayerCard) -> GachaPlayer:
    return GachaPlayer(
        name=card.name,
        position=card.position,
        rarity=card.rarity,
        base_rating=card.base_rating,
        overall=card.overall,
        pac=card.pac,
        sho=card.sho,
        pas=card.pas,
        dri=card.dri,
        def_stat=card.def_stat,
        phy=card.phy,
        potential=card.potential,
        age=card.age,
        date_of_birth=card.date_of_birth,
        role=card.role,
    )


def _make_player(position: str, rarity: str, names: dict[str, list[str]]) -> GachaPlayer:
    lo, hi = RARITY_RATING_RANGES[rarity]
    target = random.randint(lo, hi)
    first_name = random.choice(names["first"])
    last_name = random.choice(names["last"])
    card = create_player_card(
        position=position,
        rarity=rarity,
        target_ovr=target,
        first_name=first_name,
        last_name=last_name,
    )
    return _from_created(card)


def generate_pack(n: int | None = None, *, pack_id: str = "standard") -> GachaPack:
    """Generate a pack using named PackConfig (default: standard 60/30/8/2)."""
    cfg = get_pack_config(pack_id)
    count = cfg.card_count if n is None else n
    names = _load_names()
    players = []
    for _ in range(count):
        rarity = random.choices(list(cfg.rarities), weights=list(cfg.rarity_weights), k=1)[0]
        position = random.choices(list(cfg.positions), weights=list(cfg.position_weights), k=1)[0]
        players.append(_make_player(position, rarity, names))
    return GachaPack(players=players)


def generate_starter_squad() -> StarterSquad:
    """
    Generates a guaranteed 11-player squad for onboarding:
    - 1 Marquee: Rare (80%) or Epic (20%), non-GK position.
    - 10 Youth: All Common, covering the full 4-4-2 formation blueprint.
    """
    names = _load_names()

    marquee_rarity = random.choices(["Rare", "Epic"], weights=[80, 20], k=1)[0]
    marquee_position = random.choice(_MARQUEE_POSITIONS)
    marquee = _make_player(marquee_position, marquee_rarity, names)

    full_common_positions = list(_YOUTH_POSITIONS)
    full_common_positions.remove(marquee_position)

    youth = [_make_player(pos, "Common", names) for pos in full_common_positions]

    return StarterSquad(marquee=marquee, youth=youth)


def generate_youth_intake(count: int | None = None, *, academy_level: int = 1) -> list[GachaPlayer]:
    """Seasonal academy intake — quality scales with Youth Academy level (Phase C)."""
    names = _load_names()
    rows = generate_youth_intake_cards(
        count,
        academy_level=academy_level,
        first_names=names["first"],
        last_names=names["last"],
    )
    return [_from_created(row) for row in rows]
