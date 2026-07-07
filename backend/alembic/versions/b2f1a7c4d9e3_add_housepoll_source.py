"""add HousePoll.source column

Distinguishes the two district-poll ingestion streams: Wikipedia state-page
scraping (house_polls.py) and VoteHub's us-representative polls (votehub.py).
Additive and safe on existing rows — the server default backfills them as
"wikipedia", which is accurate since VoteHub ingestion didn't exist before this.

Revision ID: b2f1a7c4d9e3
Revises: 1cfc95e31a13
Create Date: 2026-07-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2f1a7c4d9e3'
down_revision: Union[str, None] = '1cfc95e31a13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'house_polls',
        sa.Column('source', sa.String(length=16), nullable=False,
                  server_default='wikipedia'),
    )


def downgrade() -> None:
    op.drop_column('house_polls', 'source')
