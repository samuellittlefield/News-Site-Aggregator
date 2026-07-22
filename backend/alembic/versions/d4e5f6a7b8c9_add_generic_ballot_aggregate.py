"""add GenericBallotAggregate table (persisted generic-ballot aggregator rows)

Additive-only: creates the `generic_ballot_aggregates` table used by the
forecast-model-swing-fallback-fix to give `_current_env()` a DB-only fallback
tier when VoteHub's generic-ballot window is empty. Safe on existing data —
nothing existing is touched, and the table starts empty until the next
`refresh_house_polls` run persists rows into it, so no backfill is needed.

Revision ID: d4e5f6a7b8c9
Revises: c3d2e5f6a7b8
Create Date: 2026-07-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d2e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'generic_ballot_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('rep', sa.Float(), nullable=False),
        sa.Column('dem', sa.Float(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', name='generic_ballot_aggregates_source_key'),
    )
    op.create_index(op.f('ix_generic_ballot_aggregates_id'), 'generic_ballot_aggregates', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_generic_ballot_aggregates_id'), table_name='generic_ballot_aggregates')
    op.drop_table('generic_ballot_aggregates')
