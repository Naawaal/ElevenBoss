import unittest
import asyncio
from unittest.mock import MagicMock

# Mock asyncio.get_running_loop() before importing any discord.ui components
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

import pytest
import discord
from app.ui.renderers.club_renderer import render_locker_room, render_club_dashboard
from app.ui.layouts.locker_room import build_locker_room_layout
from app.ui.layouts.club_dashboard import build_club_dashboard_layout
from app.ui.components import V2View

@pytest.fixture
def sample_club_data():
    return {
        "club_id": "8cf552a8-1234-4bc9-90c9-e6f1e19e8578",
        "club_name": "Test Club FC",
        "budget": 25000000,
        "reputation": 3.5,
        "stadium_capacity": 45000,
        "squad_size": 25,
        "average_overall": 76.5,
        "best_player_name": "John Doe",
        "best_player_ovr": 85,
        "highest_pot_name": "Jane Smith",
        "highest_pot_val": 92,
        "league_status": "Champions League (Season 1)",
        "next_suggested_action": "Check your team lineup or recruit players.",
        "discord_user_id": "1234567890",
        "guild_id": "987654321"
    }

def test_build_locker_room_layout_with_and_without_image(sample_club_data):
    nonce = "test-nonce"
    # Without image
    view_no_img = build_locker_room_layout(sample_club_data, nonce, has_image=False)
    assert isinstance(view_no_img, V2View)
    # Check that it contains container component and text_display
    has_text = False
    for comp in view_no_img.to_components():
        if comp.get("type") == 17:  # Container
            for child in comp.get("components", []):
                if child.get("type") == 10:  # TextDisplay
                    has_text = True
    assert has_text

    # With image
    view_with_img = build_locker_room_layout(sample_club_data, nonce, has_image=True)
    assert isinstance(view_with_img, V2View)
    has_gallery = False
    for comp in view_with_img.to_components():
        if comp.get("type") == 12:  # Media Gallery
            has_gallery = True
    assert has_gallery

def test_build_club_dashboard_layout_with_and_without_image(sample_club_data):
    nonce = "test-nonce"
    # Without image
    view_no_img = build_club_dashboard_layout(sample_club_data, nonce, has_image=False)
    assert isinstance(view_no_img, V2View)
    
    # With image
    view_with_img = build_club_dashboard_layout(sample_club_data, nonce, has_image=True)
    assert isinstance(view_with_img, V2View)
    has_gallery = False
    for comp in view_with_img.to_components():
        if comp.get("type") == 12:  # Media Gallery
            has_gallery = True
    assert has_gallery

def test_render_locker_room_returns_tuple_with_file(sample_club_data):
    nonce = "test-nonce"
    res = render_locker_room(sample_club_data, nonce)
    assert isinstance(res, tuple)
    view, file = res
    assert isinstance(view, V2View)
    assert file is None

def test_render_club_dashboard_returns_tuple_with_file(sample_club_data):
    nonce = "test-nonce"
    res = render_club_dashboard(sample_club_data, nonce)
    assert isinstance(res, tuple)
    view, file = res
    assert isinstance(view, V2View)
    assert file is None
