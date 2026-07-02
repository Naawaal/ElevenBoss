"""add_league_lifecycle_fields

Revision ID: c1d2e3f4a5b6
Revises: a2b3c4d5e6f7
Create Date: 2026-07-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update league_status enum values (safely Renaming to lowercase for PostgreSQL)
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == 'postgresql':
        op.execute("COMMIT")
        
        # Safe helper to rename enum values only if they exist in pg_enum
        def rename_enum_value_if_exists(enum_name: str, old_val: str, new_val: str):
            # Check existence
            exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_enum e "
                "JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = :typname AND e.enumlabel = :label"
            ), {"typname": enum_name, "label": old_val}).scalar()
            
            if exists:
                op.execute(f"ALTER TYPE {enum_name} RENAME VALUE '{old_val}' TO '{new_val}'")

        # 1. Update league_status enum values to lowercase
        for old, new in [('DRAFT', 'draft'), ('ACTIVE', 'active'), ('COMPLETED', 'completed'), ('ARCHIVED', 'archived')]:
            rename_enum_value_if_exists('league_status', old, new)

        # 2. Update season_status enum values to lowercase
        for old, new in [('DRAFT', 'draft'), ('ACTIVE', 'active'), ('COMPLETED', 'completed'), ('ARCHIVED', 'archived')]:
            rename_enum_value_if_exists('season_status', old, new)

        # 3. Update scheduler_run_status enum values to lowercase
        for old, new in [('RUNNING', 'running'), ('SUCCESS', 'success'), ('FAILED', 'failed'), ('SKIPPED', 'skipped')]:
            rename_enum_value_if_exists('scheduler_run_status', old, new)

        # 4. Update fixture_status enum values to lowercase
        for old, new in [('SCHEDULED', 'scheduled'), ('LOCKED', 'locked'), ('SIMULATING', 'simulating'), ('PLAYED', 'played'), ('VOID', 'void')]:
            rename_enum_value_if_exists('fixture_status', old, new)

        # 5. Update match_event_type enum values to lowercase
        for old, new in [
            ('GOAL', 'goal'), ('ASSIST', 'assist'), ('YELLOW_CARD', 'yellow_card'),
            ('RED_CARD', 'red_card'), ('INJURY', 'injury'), ('SUBSTITUTION', 'substitution'),
            ('VAR', 'var'), ('PENALTY', 'penalty'), ('OWN_GOAL', 'own_goal'),
            ('MATCH_START', 'match_start'), ('HALF_TIME', 'half_time'), ('FULL_TIME', 'full_time')
        ]:
            rename_enum_value_if_exists('match_event_type', old, new)

        # Add new lifecycle statuses to league_status type
        op.execute("ALTER TYPE league_status ADD VALUE IF NOT EXISTS 'starting'")
        op.execute("ALTER TYPE league_status ADD VALUE IF NOT EXISTS 'needs_admin_review'")
        op.execute("ALTER TYPE league_status ADD VALUE IF NOT EXISTS 'cancelled'")

    # 2. Add settings and deadline columns to leagues table safely if they do not exist
    inspector = sa.inspect(bind)
    existing_cols = [c['name'] for c in inspector.get_columns('leagues')]

    def add_col_safe(col):
        if col.name not in existing_cols:
            op.add_column('leagues', col)

    add_col_safe(sa.Column('registration_deadline_at', sa.DateTime(timezone=True), nullable=True))
    add_col_safe(sa.Column('registration_deadline_timezone', sa.String(length=64), nullable=True))
    add_col_safe(sa.Column('auto_start_after_deadline', sa.Boolean(), server_default='true', nullable=False))
    add_col_safe(sa.Column('fill_bots_after_deadline', sa.Boolean(), server_default='true', nullable=False))
    add_col_safe(sa.Column('minimum_human_clubs', sa.Integer(), server_default='2', nullable=False))
    add_col_safe(sa.Column('target_club_count', sa.Integer(), server_default='8', nullable=False))
    add_col_safe(sa.Column('review_reason', sa.String(length=256), nullable=True))

    # 3. Add partial unique index safely if it does not exist
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('leagues')]
    if 'uq_active_league_guild' not in existing_indexes:
        if dialect_name == 'postgresql':
            op.create_index('uq_active_league_guild', 'leagues', ['guild_id'], unique=True, postgresql_where=sa.text("status NOT IN ('cancelled', 'completed')"))
        elif dialect_name == 'sqlite':
            op.create_index('uq_active_league_guild', 'leagues', ['guild_id'], unique=True, sqlite_where=sa.text("status NOT IN ('cancelled', 'completed')"))
        else:
            op.create_index('uq_active_league_guild', 'leagues', ['guild_id'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    # Drop index
    op.drop_index('uq_active_league_guild', table_name='leagues')

    # Drop columns
    op.drop_column('leagues', 'review_reason')
    op.drop_column('leagues', 'target_club_count')
    op.drop_column('leagues', 'minimum_human_clubs')
    op.drop_column('leagues', 'fill_bots_after_deadline')
    op.drop_column('leagues', 'auto_start_after_deadline')
    op.drop_column('leagues', 'registration_deadline_timezone')
    op.drop_column('leagues', 'registration_deadline_at')
