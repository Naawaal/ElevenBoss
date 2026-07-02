import pytest
import uuid
import random
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.player import Player
from app.models.club import Club
from app.services.player_service import PlayerService
from app.engine.player_generator import REGIONAL_NAME_POOLS, generate_squad, generate_player

@pytest.mark.asyncio
async def test_proportional_tier_allocation_and_determinism():
    # Test that squad generation is position-aware and tier-balanced
    guild_id = "test_guild"
    club_id = uuid.uuid4()
    
    # Run with seed
    squad_1 = generate_squad(guild_id, club_id, seed=42)
    squad_2 = generate_squad(guild_id, club_id, seed=42)
    
    # Assert determinism
    assert len(squad_1) == 25
    assert len(squad_2) == 25
    for p1, p2 in zip(squad_1, squad_2):
        assert p1.display_name == p2.display_name
        assert p1.position == p2.position
        assert p1.overall == p2.overall
        assert p1.potential == p2.potential
        assert p1.nationality == p2.nationality
        assert p1.traits == p2.traits

    # Verify tier sizes
    # Star: 1 (72-78), Key: 4 (66-71), Rotation: 12 (60-65), Prospect: 8 (48-59)
    star_count = 0
    key_count = 0
    rotation_count = 0
    prospect_count = 0
    
    for p in squad_1:
        # Check nationality exists in pools
        assert p.nationality in REGIONAL_NAME_POOLS
        pool = REGIONAL_NAME_POOLS[p.nationality]
        assert p.first_name in pool["first_names"]
        assert p.last_name in pool["last_names"]
        
        # Check overall tiers
        if 72 <= p.overall <= 78:
            star_count += 1
        elif 66 <= p.overall <= 71:
            key_count += 1
        elif 60 <= p.overall <= 65:
            rotation_count += 1
        elif 48 <= p.overall <= 59:
            prospect_count += 1
        else:
            pytest.fail(f"Invalid overall rating: {p.overall}")
            
    assert star_count == 1
    assert key_count == 4
    assert rotation_count == 12
    assert prospect_count == 8

    # Verify no position group is entirely prospect-tier (at least one rotation-or-better player)
    groups = {
        "GK": ["GK"],
        "DEF": ["CB", "LB", "RB", "LWB", "RWB"],
        "MID": ["CDM", "CM", "CAM", "LM", "RM"],
        "ATT": ["LW", "RW", "ST", "CF"]
    }
    for group_name, positions in groups.items():
        group_players = [p for p in squad_1 if p.position in positions]
        rotation_or_better = [p for p in group_players if p.overall >= 60]
        assert len(rotation_or_better) > 0, f"Group {group_name} has no rotation-or-better players!"

@pytest.mark.asyncio
async def test_position_correlated_traits():
    squad = generate_squad("test_guild", uuid.uuid4(), seed=10)
    
    UNIVERSAL_TRAITS = {"leader", "consistent", "injury_prone", "one_club_player"}
    ATTACKER_TRAITS = {"clinical_finisher", "pacey", "big_game_player"}.union(UNIVERSAL_TRAITS)
    MIDFIELDER_TRAITS = {"playmaker"}.union(UNIVERSAL_TRAITS)
    DEFENDER_GK_TRAITS = {"ball_winner", "aerial_threat"}.union(UNIVERSAL_TRAITS)
    
    for p in squad:
        traits_list = p.traits.get("list", [])
        if p.position in ["GK", "CB", "LB", "RB", "LWB", "RWB"]:
            for trait in traits_list:
                assert trait in DEFENDER_GK_TRAITS, f"GK/DEF player {p.display_name} has invalid trait: {trait}"
        elif p.position in ["CDM", "CM", "CAM", "LM", "RM"]:
            for trait in traits_list:
                assert trait in MIDFIELDER_TRAITS, f"MID player {p.display_name} has invalid trait: {trait}"
        else:  # LW, RW, ST, CF
            for trait in traits_list:
                assert trait in ATTACKER_TRAITS, f"ATT player {p.display_name} has invalid trait: {trait}"

@pytest.mark.asyncio
async def test_apply_growth_and_retirement():
    # 1. Test growth curve for young players
    young_player = Player(
        age=20,
        overall=60,
        potential=80,
        value=0,
        wage=0,
        is_retired=False
    )
    old_value = young_player.value
    old_wage = young_player.wage
    
    # Growth pass
    await PlayerService.apply_growth(young_player)
    assert young_player.overall >= 60
    assert young_player.overall <= young_player.potential
    # Value and wage must be updated/recalculated
    assert young_player.value > old_value
    assert young_player.wage > old_wage

    # 2. Test decline for old players
    veteran_player = Player(
        age=34,
        overall=70,
        potential=72,
        value=0,
        wage=0,
        is_retired=False
    )
    await PlayerService.apply_growth(veteran_player)
    assert veteran_player.overall < 70
    
    # 3. Test retirement checks
    p_35 = Player(age=35, overall=50)
    assert not await PlayerService.check_retirement(p_35)
    
    p_36_low = Player(age=36, overall=55)
    assert await PlayerService.check_retirement(p_36_low)
    
    p_36_high = Player(age=36, overall=56)
    assert not await PlayerService.check_retirement(p_36_high)
    
    p_38_high = Player(age=38, overall=80)
    assert await PlayerService.check_retirement(p_38_high)

@pytest.mark.asyncio
@patch("app.services.player_service.generate_player")
async def test_age_players_and_backfill(mock_gen_player):
    session = AsyncMock()
    season_id = uuid.uuid4()
    
    # Define bot club and human club
    bot_club = Club(id=uuid.uuid4(), guild_id="guild_1", is_bot_controlled=True)
    human_club = Club(id=uuid.uuid4(), guild_id="guild_1", is_bot_controlled=False)
    
    # Bot player near retirement
    bot_player = Player(
        id=uuid.uuid4(),
        guild_id="guild_1",
        club_id=bot_club.id,
        position="ST",
        age=37,
        overall=50,
        potential=50,
        is_retired=False
    )
    # Human player near retirement
    human_player = Player(
        id=uuid.uuid4(),
        guild_id="guild_1",
        club_id=human_club.id,
        position="ST",
        age=37,
        overall=50,
        potential=50,
        is_retired=False
    )
    
    # Mock query result
    mock_players = [bot_player, human_player]
    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_players
    mock_execute.scalars.return_value = mock_scalars
    session.execute = AsyncMock(return_value=mock_execute)
    
    # Setup session.get side effects for Clubs
    async def get_side_effect(model, ident):
        if model == Club:
            if ident == bot_club.id:
                return bot_club
            if ident == human_club.id:
                return human_club
        return None
    session.get.side_effect = get_side_effect
    
    # Mock generate_player to return a dummy prospect
    replacement_player = Player(
        guild_id="guild_1",
        club_id=bot_club.id,
        position="ST",
        age=18,
        overall=55,
        potential=75,
        is_retired=False
    )
    mock_gen_player.return_value = replacement_player
    
    # Run age_players
    await PlayerService.age_players(season_id, session)
    
    # Assertions
    # Both players' ages should be incremented to 38
    assert bot_player.age == 38
    assert human_player.age == 38
    
    # Both should be retired
    assert bot_player.is_retired is True
    assert human_player.is_retired is True
    
    # Bot club should be backfilled, human should not
    session.add.assert_called_once_with(replacement_player)
