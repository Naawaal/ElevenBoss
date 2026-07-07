# tests/test_leagues.py
from __future__ import annotations
import pytest
from match_engine import generate_round_robin_fixtures
from match_engine.fixture_generator import expected_fixture_counts

def test_fixture_generator_validation():
    # Odd number of teams should raise ValueError
    with pytest.raises(ValueError):
        generate_round_robin_fixtures(["1", "2", "3"])
        
    # Fewer than 2 teams should raise ValueError
    with pytest.raises(ValueError):
        generate_round_robin_fixtures(["1"])

def test_circular_fixtures_counts():
    club_ids = [str(i) for i in range(1, 9)] # 8 teams
    fixtures = generate_round_robin_fixtures(club_ids, double_round_robin=True)
    
    counts = expected_fixture_counts(8, double_round_robin=True)
    assert len(fixtures) == counts["total_fixtures"]
    assert counts["total_weeks"] == 14
    assert counts["fixtures_per_week"] == 4
    
    # Check that each team plays exactly once per week
    for week in range(1, 15):
        week_fixtures = [f for f in fixtures if f.week == week]
        assert len(week_fixtures) == 4
        
        teams_played = set()
        for f in week_fixtures:
            assert f.home_club_id not in teams_played
            assert f.away_club_id not in teams_played
            teams_played.add(f.home_club_id)
            teams_played.add(f.away_club_id)
        assert len(teams_played) == 8

def test_player_admin_split_structure():
    # Import cogs and views
    from apps.discord_bot.cogs.league_cog import LeagueCog, LeagueHubView
    from apps.discord_bot.cogs.admin_cog import AdminCog, AdminHubView, LeagueManagementView
    
    # 1. Check LeagueHubView properties
    # Should only contain player buttons (Register, View Table, My Fixtures, Season Stats)
    hub_view = LeagueHubView(None, 12345, 67890)
    button_custom_ids = [child.custom_id for child in hub_view.children if hasattr(child, "custom_id")]
    
    # Assert player buttons are present
    assert "hub_register_btn" in button_custom_ids
    assert "hub_view_table_btn" in button_custom_ids
    assert "hub_my_fixtures_btn" in button_custom_ids
    assert "hub_season_stats_btn" in button_custom_ids
    assert "hub_scout_btn" in button_custom_ids
    
    # Assert admin buttons are NOT present
    assert "league_admin_start" not in button_custom_ids
    assert "league_admin_end" not in button_custom_ids
    assert "league_admin_kick" not in button_custom_ids
    assert "league_admin_sim" not in button_custom_ids
    assert "league_admin_duration" not in button_custom_ids
    
    # 2. Check LeagueCog methods
    # Should NOT contain admin callbacks
    cog_methods = dir(LeagueCog)
    assert "admin_start_season" not in cog_methods
    assert "admin_end_season" not in cog_methods
    assert "admin_kick_menu" not in cog_methods
    assert "admin_execute_kick" not in cog_methods
    assert "admin_force_sim" not in cog_methods
    assert "admin_duration_modal" not in cog_methods
    assert "admin_execute_set_duration" not in cog_methods

    # 3. Check AdminHubView has league button enabled
    admin_view = AdminHubView(12345, 67890)
    league_button = next(child for child in admin_view.children if child.custom_id == "admin_hub_league")
    assert not league_button.disabled

