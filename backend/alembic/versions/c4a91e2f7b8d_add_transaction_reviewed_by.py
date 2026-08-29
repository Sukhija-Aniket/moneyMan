"""add transactions.reviewed_by

Revision ID: c4a91e2f7b8d
Revises: b3f2a71c9d4e
Create Date: 2026-08-28 00:00:00.000000

Distinguishes a transaction the extraction pipeline auto-confirmed (reviewed_by="system",
review_status set straight to non-"pending" without ever needing a human look) from one a
person actually acted on via PATCH /transactions/{id} (reviewed_by="human") — see
app/api/routes/transactions.py::update_transaction and
shared/moneyman_shared/services/gmail_sync.py. Lets the UI hide "Move to review" only for
transactions the user already vetted themself, not ones that were merely auto-confirmed.

Backfill: every existing non-pending row was set by the pipeline (the PATCH endpoint that
stamps "human" didn't exist before this migration), so they're all backfilled as "system".
Existing "pending" rows are left NULL (not yet reviewed either way), matching what a new
pending transaction gets going forward.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a91e2f7b8d'
down_revision: Union[str, Sequence[str], None] = 'b3f2a71c9d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transactions', sa.Column('reviewed_by', sa.String(), nullable=True))
    op.create_check_constraint(
        'ck_transactions_reviewed_by', 'transactions', "reviewed_by IN ('system', 'human')"
    )

    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE transactions SET reviewed_by = 'system' WHERE review_status != 'pending'")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_transactions_reviewed_by', 'transactions', type_='check')
    op.drop_column('transactions', 'reviewed_by')
