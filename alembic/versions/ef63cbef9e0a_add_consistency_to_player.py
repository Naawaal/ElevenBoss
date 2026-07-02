"""add_consistency_to_player

Revision ID: ef63cbef9e0a
Revises: c1d2e3f4a5b6
Create Date: 2026-07-02 13:26:03.083703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef63cbef9e0a'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add column as nullable first
    op.add_column('players', sa.Column('consistency', sa.Integer(), nullable=True))
    # Populate existing rows with default value of 70
    op.execute("UPDATE players SET consistency = 70 WHERE consistency IS NULL")
    # Alter column to be NOT NULL
    op.alter_column('players', 'consistency', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('players', 'consistency')
