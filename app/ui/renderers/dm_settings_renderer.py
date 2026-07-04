# app/ui/renderers/dm_settings_renderer.py

from app.ui.layouts.dm_settings import (
    build_dm_server_picker,
    build_settings_overview_layout,
    build_settings_channels_layout,
    build_settings_admin_role_layout,
    build_settings_automation_layout,
    build_settings_schedule_layout,
    build_settings_matchday_layout,
)
from app.ui.components import V2View

def render_dm_server_picker(guild_views, nonce: str) -> V2View:
    return build_dm_server_picker(guild_views, nonce)

def render_settings_overview(config, guild_name: str, league_status: str, season_week: str, next_run_str: str, admin_role_name: str, mention_role_name: str, nonce: str, is_admin: bool) -> V2View:
    return build_settings_overview_layout(config, guild_name, league_status, season_week, next_run_str, admin_role_name, mention_role_name, is_admin, nonce)

def render_settings_channels(config, guild_name: str, guild_channels, nonce: str, is_admin: bool) -> V2View:
    return build_settings_channels_layout(config, guild_name, guild_channels, is_admin, nonce)

def render_settings_admin_role(config, guild_name: str, guild_roles, nonce: str, is_admin: bool) -> V2View:
    return build_settings_admin_role_layout(config, guild_name, guild_roles, is_admin, nonce)

def render_settings_automation(config, guild_name: str, nonce: str, is_admin: bool) -> V2View:
    return build_settings_automation_layout(config, guild_name, is_admin, nonce)

def render_settings_schedule(config, guild_name: str, next_run_str: str, nonce: str, is_admin: bool) -> V2View:
    return build_settings_schedule_layout(config, guild_name, next_run_str, is_admin, nonce)

def render_settings_matchday(config, guild_name: str, league_status: str, season_week: str, fixtures_stats: dict, nonce: str, is_admin: bool) -> V2View:
    return build_settings_matchday_layout(config, guild_name, league_status, season_week, fixtures_stats, is_admin, nonce)
