"""add_mention_role_id_to_guild_configs

Revision ID: 074075796416
Revises: d1e2f3a4b5c6
Create Date: 2026-07-04 15:40:03.694758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '074075796416'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('guild_configs', sa.Column('mention_role_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('guild_configs', 'mention_role_id')
