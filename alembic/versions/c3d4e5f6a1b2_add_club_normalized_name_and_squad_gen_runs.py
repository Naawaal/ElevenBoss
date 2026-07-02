"""add_club_normalized_name_and_squad_gen_runs

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-07-02 16:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Add normalized_name to clubs (nullable first, backfill, then NOT NULL).
    2. Add unique index on (guild_id, normalized_name) for clubs.
    3. Create squad_generation_runs table.
    """
    # 1. Add as nullable
    op.add_column('clubs', sa.Column('normalized_name', sa.String(length=128), nullable=True))

    # 2. Backfill: lowercase + collapse whitespace using regexp_replace
    op.execute(
        """
        UPDATE clubs
        SET normalized_name = lower(trim(regexp_replace(name, '\\s+', ' ', 'g')))
        WHERE normalized_name IS NULL
        """
    )

    # 3. Alter to NOT NULL
    op.alter_column('clubs', 'normalized_name', nullable=False)

    # 4. Create unique index
    op.create_index('ix_clubs_normalized_name', 'clubs', ['normalized_name'])
    op.create_unique_constraint(
        'uq_club_guild_normalized_name', 'clubs', ['guild_id', 'normalized_name']
    )

    # 5. Create squad_generation_runs table
    op.create_table(
        'squad_generation_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('generation_key', sa.String(length=256), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('club_id', name='uq_squad_gen_run_club_id'),
        sa.UniqueConstraint('generation_key', name='uq_squad_gen_run_key'),
    )
    op.create_index('ix_squad_generation_runs_club_id', 'squad_generation_runs', ['club_id'])


def downgrade() -> None:
    """Reverse all changes."""
    op.drop_table('squad_generation_runs')
    op.drop_constraint('uq_club_guild_normalized_name', 'clubs', type_='unique')
    op.drop_index('ix_clubs_normalized_name', table_name='clubs')
    op.drop_column('clubs', 'normalized_name')
