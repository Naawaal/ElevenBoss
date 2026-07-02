"""add_onboarding_sessions

Revision ID: a1b2c3d4e5f6
Revises: f2a7b6d1e4c9
Create Date: 2026-07-02 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f2a7b6d1e4c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create onboarding_sessions table with all required indexes."""
    op.create_table(
        'onboarding_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('guild_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('channel_id', sa.String(length=64), nullable=True),
        sa.Column('thread_id', sa.String(length=64), nullable=True),
        sa.Column('starter_message_id', sa.String(length=64), nullable=True),
        sa.Column('flow_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('current_step', sa.String(length=64), nullable=False),
        sa.Column('collected_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('status_reason', sa.Text(), nullable=True),
        sa.Column('club_id', sa.Uuid(), nullable=True),
        sa.Column('thread_mode', sa.String(length=16), nullable=True),
        sa.Column('visibility_warning_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('nudge_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completing_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('abandoned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cleanup_after', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cleanup_attempted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cleanup_error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # guild_id, user_id sweep indexes
    op.create_index('ix_onboarding_sessions_guild_id', 'onboarding_sessions', ['guild_id'])
    op.create_index('ix_onboarding_sessions_user_id', 'onboarding_sessions', ['user_id'])
    op.create_index('ix_onboarding_sessions_thread_id', 'onboarding_sessions', ['thread_id'])

    # Partial unique: at most one ACTIVE or COMPLETING session per (guild, user)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_onboarding_active_per_user
        ON onboarding_sessions (guild_id, user_id)
        WHERE status IN ('ACTIVE', 'COMPLETING')
        """
    )

    # Sweeper index: find active sessions by last_activity_at
    op.execute(
        """
        CREATE INDEX idx_onboarding_active_sweep
        ON onboarding_sessions (status, last_activity_at)
        WHERE status = 'ACTIVE'
        """
    )

    # Sweeper index: find sessions due for cleanup
    op.execute(
        """
        CREATE INDEX idx_onboarding_cleanup_due
        ON onboarding_sessions (cleanup_after)
        WHERE cleanup_after IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop onboarding_sessions and all its indexes."""
    op.execute("DROP INDEX IF EXISTS idx_onboarding_cleanup_due")
    op.execute("DROP INDEX IF EXISTS idx_onboarding_active_sweep")
    op.execute("DROP INDEX IF EXISTS uq_onboarding_active_per_user")
    op.drop_index('ix_onboarding_sessions_thread_id', table_name='onboarding_sessions')
    op.drop_index('ix_onboarding_sessions_user_id', table_name='onboarding_sessions')
    op.drop_index('ix_onboarding_sessions_guild_id', table_name='onboarding_sessions')
    op.drop_table('onboarding_sessions')
