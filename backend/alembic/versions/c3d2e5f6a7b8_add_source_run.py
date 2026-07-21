"""add SourceRun table (per-source ingestion health)

Additive-only: creates the `source_runs` table used by the ingestion-health
feature to record one upserted current-state row per scheduler job id. Safe on
existing data — nothing existing is touched, and the table starts empty (the
route synthesises a "never_run" state for any registered source without a row
yet, per ingestion-health AC-6), so no backfill is needed.

Revision ID: c3d2e5f6a7b8
Revises: b2f1a7c4d9e3
Create Date: 2026-07-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d2e5f6a7b8'
down_revision: Union[str, None] = 'b2f1a7c4d9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'source_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='never_run'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('item_count', sa.Integer(), nullable=True),
        sa.Column('cadence_minutes', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', name='source_runs_source_id_key'),
    )
    op.create_index(op.f('ix_source_runs_id'), 'source_runs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_source_runs_id'), table_name='source_runs')
    op.drop_table('source_runs')
