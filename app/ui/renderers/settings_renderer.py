# app/ui/renderers/settings_renderer.py

from app.ui.layouts.settings import (
    build_settings_overview_layout,
    build_settings_channels_layout,
    build_settings_admin_role_layout,
    build_settings_automation_layout,
    build_settings_schedule_layout,
    build_settings_matchday_layout,
)
from app.ui.components import V2View

def render_settings_overview(config, league_status: str, season_week: str, next_run_str: str, nonce: str, is_admin: bool) -> V2View:
    return build_settings_overview_layout(config, league_status, season_week, next_run_str, is_admin, nonce)

def render_settings_channels(config, nonce: str, is_admin: bool) -> V2View:
    return build_settings_channels_layout(config, is_admin, nonce)

def render_settings_admin_role(config, nonce: str, is_admin: bool) -> V2View:
    return build_settings_admin_role_layout(config, is_admin, nonce)

def render_settings_automation(config, nonce: str, is_admin: bool) -> V2View:
    return build_settings_automation_layout(config, is_admin, nonce)

def render_settings_schedule(config, next_run_str: str, nonce: str, is_admin: bool) -> V2View:
    return build_settings_schedule_layout(config, next_run_str, is_admin, nonce)

def render_settings_matchday(config, league_status: str, season_week: str, fixtures_stats: dict, nonce: str, is_admin: bool) -> V2View:
    return build_settings_matchday_layout(config, league_status, season_week, fixtures_stats, is_admin, nonce)
