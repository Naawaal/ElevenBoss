"""add_automation_fields_to_guild_config

Revision ID: a2b3c4d5e6f7
Revises: b511c80ca0cd
Create Date: 2026-07-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'b511c80ca0cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('guild_configs', sa.Column('auto_join_draft_league', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('guild_configs', sa.Column('auto_start_league', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('guild_configs', sa.Column('auto_fill_with_bot_clubs', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('guild_configs', sa.Column('minimum_human_clubs', sa.Integer(), server_default='2', nullable=False))
    op.add_column('guild_configs', sa.Column('registration_deadline', sa.DateTime(timezone=True), nullable=True))
    op.add_column('guild_configs', sa.Column('matchday_day', sa.String(length=32), nullable=True))
    op.add_column('guild_configs', sa.Column('matchday_time', sa.String(length=32), nullable=True))
    op.add_column('guild_configs', sa.Column('matchday_timezone', sa.String(length=64), server_default='Asia/Kathmandu', nullable=False))
    op.add_column('guild_configs', sa.Column('matchday_announcement_channel_id', sa.String(length=64), nullable=True))
    op.add_column('guild_configs', sa.Column('automation_status', sa.String(length=32), server_default='idle', nullable=False))
    op.add_column('guild_configs', sa.Column('last_automation_run_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('guild_configs', sa.Column('last_automation_status', sa.String(length=64), nullable=True))
    op.add_column('guild_configs', sa.Column('last_automation_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('guild_configs', 'last_automation_error')
    op.drop_column('guild_configs', 'last_automation_status')
    op.drop_column('guild_configs', 'last_automation_run_at')
    op.drop_column('guild_configs', 'automation_status')
    op.drop_column('guild_configs', 'matchday_announcement_channel_id')
    op.drop_column('guild_configs', 'matchday_timezone')
    op.drop_column('guild_configs', 'matchday_time')
    op.drop_column('guild_configs', 'matchday_day')
    op.drop_column('guild_configs', 'registration_deadline')
    op.drop_column('guild_configs', 'minimum_human_clubs')
    op.drop_column('guild_configs', 'auto_fill_with_bot_clubs')
    op.drop_column('guild_configs', 'auto_start_league')
    op.drop_column('guild_configs', 'auto_join_draft_league')
