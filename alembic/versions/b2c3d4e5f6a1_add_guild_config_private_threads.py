"""add_guild_config_private_threads

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02 16:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add supports_private_threads nullable column to guild_configs."""
    op.add_column(
        'guild_configs',
        sa.Column('supports_private_threads', sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    """Remove supports_private_threads column."""
    op.drop_column('guild_configs', 'supports_private_threads')
