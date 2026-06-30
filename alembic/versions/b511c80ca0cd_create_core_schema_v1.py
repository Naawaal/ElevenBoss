"""create_core_schema_v1

Revision ID: b511c80ca0cd
Revises: 
Create Date: 2026-06-30 19:35:46.834995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b511c80ca0cd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. guild_configs
    op.create_table('guild_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('game_channel_id', sa.String(length=64), nullable=True),
        sa.Column('admin_role_id', sa.String(length=64), nullable=True),
        sa.Column('default_league_size', sa.Integer(), nullable=False),
        sa.Column('matchday_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guild_configs_guild_id'), 'guild_configs', ['guild_id'], unique=True)

    # 2. leagues
    op.create_table('leagues',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('max_clubs', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'ACTIVE', 'COMPLETED', 'ARCHIVED', name='league_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'name', name='uq_league_guild_name')
    )
    op.create_index(op.f('ix_leagues_guild_id'), 'leagues', ['guild_id'], unique=False)

    # 3. seasons
    op.create_table('seasons',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('league_id', sa.Uuid(), nullable=False),
        sa.Column('season_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'ACTIVE', 'COMPLETED', 'ARCHIVED', name='season_status'), nullable=False),
        sa.Column('current_week', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('league_id', 'season_number', name='uq_season_league_number')
    )
    op.create_index(op.f('ix_seasons_guild_id'), 'seasons', ['guild_id'], unique=False)
    op.create_index(op.f('ix_seasons_league_id'), 'seasons', ['league_id'], unique=False)

    # 4. scheduler_runs
    op.create_table('scheduler_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=True),
        sa.Column('job_key', sa.String(length=256), nullable=False),
        sa.Column('job_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED', name='scheduler_run_status'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_key'),
        sa.UniqueConstraint('job_key', name='uq_scheduler_run_job_key')
    )
    op.create_index(op.f('ix_scheduler_runs_guild_id'), 'scheduler_runs', ['guild_id'], unique=False)

    # 5. clubs (excluding manager_id FK to avoid circular reference on creation)
    op.create_table('clubs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('league_id', sa.Uuid(), nullable=True),
        sa.Column('season_id', sa.Uuid(), nullable=True),
        sa.Column('manager_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('short_name', sa.String(length=32), nullable=True),
        sa.Column('is_bot_controlled', sa.Boolean(), nullable=False),
        sa.Column('budget', sa.BigInteger(), nullable=False),
        sa.Column('reputation', sa.Integer(), nullable=False),
        sa.Column('stadium_capacity', sa.Integer(), nullable=False),
        sa.Column('overall_rating', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'name', name='uq_club_guild_name')
    )
    op.create_index(op.f('ix_clubs_guild_id'), 'clubs', ['guild_id'], unique=False)
    op.create_index(op.f('ix_clubs_league_id'), 'clubs', ['league_id'], unique=False)
    op.create_index(op.f('ix_clubs_manager_id'), 'clubs', ['manager_id'], unique=False)
    op.create_index(op.f('ix_clubs_season_id'), 'clubs', ['season_id'], unique=False)

    # 6. managers (can have club_id FK since clubs exists)
    op.create_table('managers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('discord_user_id', sa.String(length=64), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=True),
        sa.Column('reputation', sa.Integer(), nullable=False),
        sa.Column('coins', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'discord_user_id', name='uq_manager_guild_user')
    )
    op.create_index(op.f('ix_managers_discord_user_id'), 'managers', ['discord_user_id'], unique=False)
    op.create_index(op.f('ix_managers_guild_id'), 'managers', ['guild_id'], unique=False)

    # 7. Add the clubs -> managers foreign key now that both tables exist
    op.create_foreign_key('fk_clubs_manager_id', 'clubs', 'managers', ['manager_id'], ['id'], ondelete='SET NULL')

    # 8. lineups
    op.create_table('lineups',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('formation', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("formation IN ('4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '5-3-2')", name='chk_lineup_formation'),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lineups_club_id'), 'lineups', ['club_id'], unique=False)
    op.create_index(op.f('ix_lineups_guild_id'), 'lineups', ['guild_id'], unique=False)
    op.create_index('uq_active_lineup', 'lineups', ['club_id'], unique=True, postgresql_where='is_active = true')

    # 9. players
    op.create_table('players',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=True),
        sa.Column('first_name', sa.String(length=64), nullable=False),
        sa.Column('last_name', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('position', sa.String(length=10), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('overall', sa.Integer(), nullable=False),
        sa.Column('potential', sa.Integer(), nullable=False),
        sa.Column('value', sa.BigInteger(), nullable=False),
        sa.Column('wage', sa.Integer(), nullable=False),
        sa.Column('fitness', sa.Integer(), nullable=False),
        sa.Column('sharpness', sa.Integer(), nullable=False),
        sa.Column('morale', sa.Integer(), nullable=False),
        sa.Column('preferred_foot', sa.String(length=10), nullable=False),
        sa.Column('weak_foot', sa.Integer(), nullable=False),
        sa.Column('skill_moves', sa.Integer(), nullable=False),
        sa.Column('traits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_retired', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("position IN ('GK', 'CB', 'LB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF')", name='chk_player_position'),
        sa.CheckConstraint("preferred_foot IN ('Left', 'Right')", name='chk_player_preferred_foot'),
        sa.CheckConstraint('skill_moves BETWEEN 1 AND 5', name='chk_player_skill_moves'),
        sa.CheckConstraint('weak_foot BETWEEN 1 AND 5', name='chk_player_weak_foot'),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_players_club_id'), 'players', ['club_id'], unique=False)
    op.create_index(op.f('ix_players_guild_id'), 'players', ['guild_id'], unique=False)
    op.create_index(op.f('ix_players_overall'), 'players', ['overall'], unique=False)
    op.create_index(op.f('ix_players_position'), 'players', ['position'], unique=False)
    op.create_index(op.f('ix_players_potential'), 'players', ['potential'], unique=False)

    # 10. lineup_players
    op.create_table('lineup_players',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('lineup_id', sa.Uuid(), nullable=False),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('slot', sa.String(length=32), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('is_starter', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lineup_id'], ['lineups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lineup_id', 'player_id', name='uq_lineup_player_link'),
        sa.UniqueConstraint('lineup_id', 'slot', name='uq_lineup_player_slot')
    )
    op.create_index(op.f('ix_lineup_players_guild_id'), 'lineup_players', ['guild_id'], unique=False)
    op.create_index(op.f('ix_lineup_players_lineup_id'), 'lineup_players', ['lineup_id'], unique=False)
    op.create_index(op.f('ix_lineup_players_player_id'), 'lineup_players', ['player_id'], unique=False)

    # 11. fixtures
    op.create_table('fixtures',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('season_id', sa.Uuid(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('home_club_id', sa.Uuid(), nullable=False),
        sa.Column('away_club_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.Enum('SCHEDULED', 'LOCKED', 'SIMULATING', 'PLAYED', 'VOID', name='fixture_status'), nullable=False),
        sa.Column('home_goals', sa.Integer(), nullable=True),
        sa.Column('away_goals', sa.Integer(), nullable=True),
        sa.Column('simulation_seed', sa.String(length=64), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('played_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['away_club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['home_club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season_id', 'week', 'home_club_id', 'away_club_id', name='uq_fixture_week_clubs')
    )
    op.create_index(op.f('ix_fixtures_guild_id'), 'fixtures', ['guild_id'], unique=False)
    op.create_index(op.f('ix_fixtures_season_id'), 'fixtures', ['season_id'], unique=False)
    op.create_index(op.f('ix_fixtures_status'), 'fixtures', ['status'], unique=False)
    op.create_index(op.f('ix_fixtures_week'), 'fixtures', ['week'], unique=False)

    # 12. league_standings
    op.create_table('league_standings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('season_id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('played', sa.Integer(), nullable=False),
        sa.Column('wins', sa.Integer(), nullable=False),
        sa.Column('draws', sa.Integer(), nullable=False),
        sa.Column('losses', sa.Integer(), nullable=False),
        sa.Column('goals_for', sa.Integer(), nullable=False),
        sa.Column('goals_against', sa.Integer(), nullable=False),
        sa.Column('goal_difference', sa.Integer(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season_id', 'club_id', name='uq_standing_season_club')
    )
    op.create_index(op.f('ix_league_standings_club_id'), 'league_standings', ['club_id'], unique=False)
    op.create_index(op.f('ix_league_standings_guild_id'), 'league_standings', ['guild_id'], unique=False)
    op.create_index(op.f('ix_league_standings_season_id'), 'league_standings', ['season_id'], unique=False)

    # 13. match_results
    op.create_table('match_results',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('fixture_id', sa.Uuid(), nullable=False),
        sa.Column('home_club_id', sa.Uuid(), nullable=False),
        sa.Column('away_club_id', sa.Uuid(), nullable=False),
        sa.Column('home_goals', sa.Integer(), nullable=False),
        sa.Column('away_goals', sa.Integer(), nullable=False),
        sa.Column('home_possession', sa.Integer(), nullable=False),
        sa.Column('away_possession', sa.Integer(), nullable=False),
        sa.Column('home_shots', sa.Integer(), nullable=False),
        sa.Column('away_shots', sa.Integer(), nullable=False),
        sa.Column('home_shots_on_target', sa.Integer(), nullable=False),
        sa.Column('away_shots_on_target', sa.Integer(), nullable=False),
        sa.Column('motm_player_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['away_club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fixture_id'], ['fixtures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['home_club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['motm_player_id'], ['players.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fixture_id')
    )
    op.create_index(op.f('ix_match_results_guild_id'), 'match_results', ['guild_id'], unique=False)

    # 14. match_events
    op.create_table('match_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('fixture_id', sa.Uuid(), nullable=False),
        sa.Column('minute', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.Enum('GOAL', 'ASSIST', 'YELLOW_CARD', 'RED_CARD', 'INJURY', 'SUBSTITUTION', 'VAR', 'PENALTY', 'OWN_GOAL', 'MATCH_START', 'HALF_TIME', 'FULL_TIME', name='match_event_type'), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=True),
        sa.Column('player_id', sa.Uuid(), nullable=True),
        sa.Column('secondary_player_id', sa.Uuid(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fixture_id'], ['fixtures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['secondary_player_id'], ['players.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_events_fixture_id'), 'match_events', ['fixture_id'], unique=False)
    op.create_index(op.f('ix_match_events_guild_id'), 'match_events', ['guild_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop circular foreign key constraint
    op.drop_constraint('fk_clubs_manager_id', 'clubs', type_='foreignkey')

    # 2. Drop tables in reverse order of creation to satisfy foreign keys
    op.drop_index(op.f('ix_match_events_guild_id'), table_name='match_events')
    op.drop_index(op.f('ix_match_events_fixture_id'), table_name='match_events')
    op.drop_table('match_events')

    op.drop_index(op.f('ix_match_results_guild_id'), table_name='match_results')
    op.drop_table('match_results')

    op.drop_index(op.f('ix_league_standings_season_id'), table_name='league_standings')
    op.drop_index(op.f('ix_league_standings_guild_id'), table_name='league_standings')
    op.drop_index(op.f('ix_league_standings_club_id'), table_name='league_standings')
    op.drop_table('league_standings')

    op.drop_index(op.f('ix_fixtures_week'), table_name='fixtures')
    op.drop_index(op.f('ix_fixtures_status'), table_name='fixtures')
    op.drop_index(op.f('ix_fixtures_season_id'), table_name='fixtures')
    op.drop_index(op.f('ix_fixtures_guild_id'), table_name='fixtures')
    op.drop_table('fixtures')

    op.drop_index(op.f('ix_lineup_players_player_id'), table_name='lineup_players')
    op.drop_index(op.f('ix_lineup_players_lineup_id'), table_name='lineup_players')
    op.drop_index(op.f('ix_lineup_players_guild_id'), table_name='lineup_players')
    op.drop_table('lineup_players')

    op.drop_index(op.f('ix_players_potential'), table_name='players')
    op.drop_index(op.f('ix_players_position'), table_name='players')
    op.drop_index(op.f('ix_players_overall'), table_name='players')
    op.drop_index(op.f('ix_players_guild_id'), table_name='players')
    op.drop_index(op.f('ix_players_club_id'), table_name='players')
    op.drop_table('players')

    op.drop_index('uq_active_lineup', table_name='lineups', postgresql_where='is_active = true')
    op.drop_index(op.f('ix_lineups_guild_id'), table_name='lineups')
    op.drop_index(op.f('ix_lineups_club_id'), table_name='lineups')
    op.drop_table('lineups')

    op.drop_index(op.f('ix_managers_guild_id'), table_name='managers')
    op.drop_index(op.f('ix_managers_discord_user_id'), table_name='managers')
    op.drop_table('managers')

    op.drop_index(op.f('ix_clubs_season_id'), table_name='clubs')
    op.drop_index(op.f('ix_clubs_manager_id'), table_name='clubs')
    op.drop_index(op.f('ix_clubs_league_id'), table_name='clubs')
    op.drop_index(op.f('ix_clubs_guild_id'), table_name='clubs')
    op.drop_table('clubs')

    op.drop_index(op.f('ix_scheduler_runs_guild_id'), table_name='scheduler_runs')
    op.drop_table('scheduler_runs')

    op.drop_index(op.f('ix_seasons_league_id'), table_name='seasons')
    op.drop_index(op.f('ix_seasons_guild_id'), table_name='seasons')
    op.drop_table('seasons')

    op.drop_index(op.f('ix_leagues_guild_id'), table_name='leagues')
    op.drop_table('leagues')

    op.drop_index(op.f('ix_guild_configs_guild_id'), table_name='guild_configs')
    op.drop_table('guild_configs')
