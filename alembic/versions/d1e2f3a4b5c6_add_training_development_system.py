"""add_training_development_system

Revision ID: d1e2f3a4b5c6
Revises: b2cf89fb9aa0
Create Date: 2026-07-03 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'b2cf89fb9aa0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add 4 training/development tables."""

    # 1. player_development_state
    # One row per player per season. Accumulates training/match XP and tracks
    # readiness_modifier and the season-end OVR bonus lifecycle.
    op.create_table(
        'player_development_state',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('season_id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),

        # XP accumulators
        sa.Column('training_xp', sa.Integer(), server_default='0', nullable=False),
        sa.Column('match_xp', sa.Integer(), server_default='0', nullable=False),
        sa.Column('weeks_trained', sa.Integer(), server_default='0', nullable=False),

        # Current training state
        sa.Column('plan_type', sa.String(length=32), server_default='balanced', nullable=False),
        sa.Column('readiness_modifier', sa.Numeric(precision=4, scale=2), server_default='1.00', nullable=False),

        # Season-end bonus lifecycle
        sa.Column('season_bonus_applied', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('season_bonus_applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bonus_ovr_applied', sa.Integer(), server_default='0', nullable=False),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),

        # Unique: one row per player per season
        sa.UniqueConstraint('player_id', 'season_id', name='uq_dev_state_player_season'),

        # Value guards
        sa.CheckConstraint('training_xp >= 0', name='chk_dev_state_training_xp'),
        sa.CheckConstraint('match_xp >= 0', name='chk_dev_state_match_xp'),
        sa.CheckConstraint('weeks_trained >= 0', name='chk_dev_state_weeks_trained'),
        sa.CheckConstraint(
            'readiness_modifier >= 0.85 AND readiness_modifier <= 1.05',
            name='chk_dev_state_readiness',
        ),
        sa.CheckConstraint(
            "plan_type IN ('balanced', 'fitness', 'sharpness', 'tactical')",
            name='chk_dev_state_plan_type',
        ),
    )
    op.create_index(op.f('ix_player_development_state_guild_id'), 'player_development_state', ['guild_id'])
    op.create_index(op.f('ix_player_development_state_player_id'), 'player_development_state', ['player_id'])
    op.create_index(op.f('ix_player_development_state_season_id'), 'player_development_state', ['season_id'])

    # 2. club_training_settings
    # One row per human club per season. Stores the club-wide default plan and
    # training intensity configured by the manager.
    op.create_table(
        'club_training_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('season_id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),

        sa.Column('default_plan', sa.String(length=32), server_default='balanced', nullable=False),
        sa.Column('intensity', sa.String(length=16), server_default='normal', nullable=False),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id'),

        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),

        sa.UniqueConstraint('club_id', 'season_id', name='uq_training_settings_club_season'),

        sa.CheckConstraint(
            "default_plan IN ('balanced', 'fitness', 'sharpness', 'tactical')",
            name='chk_training_settings_plan',
        ),
        sa.CheckConstraint(
            "intensity IN ('light', 'normal', 'heavy')",
            name='chk_training_settings_intensity',
        ),
    )
    op.create_index(op.f('ix_club_training_settings_guild_id'), 'club_training_settings', ['guild_id'])
    op.create_index(op.f('ix_club_training_settings_club_id'), 'club_training_settings', ['club_id'])

    # 3. weekly_training_logs
    # Idempotency table for the weekly training tick.
    # UNIQUE(club_id, player_id, season_id, week) is the concurrency gate —
    # the DB constraint wins, not pre-flight application logic.
    op.create_table(
        'weekly_training_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('season_id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),

        sa.Column('plan_type', sa.String(length=32), nullable=False),
        sa.Column('intensity', sa.String(length=16), nullable=False),
        sa.Column('xp_earned', sa.Integer(), nullable=False),
        sa.Column('sharpness_delta', sa.Integer(), nullable=False),
        sa.Column('morale_delta', sa.Integer(), nullable=False),
        sa.Column('readiness_before', sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column('readiness_after', sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id'),

        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),

        # The strongest possible unique key: includes club_id to prevent cross-club collisions.
        sa.UniqueConstraint(
            'club_id', 'player_id', 'season_id', 'week',
            name='uq_weekly_log_club_player_season_week',
        ),
    )
    op.create_index(op.f('ix_weekly_training_logs_guild_id'), 'weekly_training_logs', ['guild_id'])
    op.create_index(op.f('ix_weekly_training_logs_player_id'), 'weekly_training_logs', ['player_id'])
    op.create_index(op.f('ix_weekly_training_logs_season_id'), 'weekly_training_logs', ['season_id'])

    # 4. match_development_events
    # League-only match XP records. Friendlies never create rows here because
    # FriendlyService never calls apply_league_match_consequences().
    op.create_table(
        'match_development_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('fixture_id', sa.Uuid(), nullable=False),
        sa.Column('season_id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),

        sa.Column('minutes_played', sa.Integer(), nullable=False),
        sa.Column('match_rating', sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column('xp_earned', sa.Integer(), nullable=False),
        sa.Column('reason_breakdown', postgresql.JSONB(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id'),

        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fixture_id'], ['fixtures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),

        sa.UniqueConstraint('player_id', 'fixture_id', name='uq_match_dev_player_fixture'),
    )
    op.create_index(op.f('ix_match_development_events_guild_id'), 'match_development_events', ['guild_id'])
    op.create_index(op.f('ix_match_development_events_player_id'), 'match_development_events', ['player_id'])
    op.create_index(op.f('ix_match_development_events_fixture_id'), 'match_development_events', ['fixture_id'])
    op.create_index(op.f('ix_match_development_events_season_id'), 'match_development_events', ['season_id'])


def downgrade() -> None:
    """Downgrade schema — drop training/development tables in dependency order."""
    op.drop_index(op.f('ix_match_development_events_season_id'), table_name='match_development_events')
    op.drop_index(op.f('ix_match_development_events_fixture_id'), table_name='match_development_events')
    op.drop_index(op.f('ix_match_development_events_player_id'), table_name='match_development_events')
    op.drop_index(op.f('ix_match_development_events_guild_id'), table_name='match_development_events')
    op.drop_table('match_development_events')

    op.drop_index(op.f('ix_weekly_training_logs_season_id'), table_name='weekly_training_logs')
    op.drop_index(op.f('ix_weekly_training_logs_player_id'), table_name='weekly_training_logs')
    op.drop_index(op.f('ix_weekly_training_logs_guild_id'), table_name='weekly_training_logs')
    op.drop_table('weekly_training_logs')

    op.drop_index(op.f('ix_club_training_settings_club_id'), table_name='club_training_settings')
    op.drop_index(op.f('ix_club_training_settings_guild_id'), table_name='club_training_settings')
    op.drop_table('club_training_settings')

    op.drop_index(op.f('ix_player_development_state_season_id'), table_name='player_development_state')
    op.drop_index(op.f('ix_player_development_state_player_id'), table_name='player_development_state')
    op.drop_index(op.f('ix_player_development_state_guild_id'), table_name='player_development_state')
    op.drop_table('player_development_state')
