"""add_nationality_to_player

Revision ID: f2a7b6d1e4c9
Revises: ef63cbef9e0a
Create Date: 2026-07-02 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a7b6d1e4c9'
down_revision: Union[str, Sequence[str], None] = 'ef63cbef9e0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add column as nullable first
    op.add_column('players', sa.Column('nationality', sa.String(length=64), nullable=True))
    # Populate existing rows with default value of 'British'
    op.execute("UPDATE players SET nationality = 'British' WHERE nationality IS NULL")
    # Alter column to be NOT NULL
    op.alter_column('players', 'nationality', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('players', 'nationality')
