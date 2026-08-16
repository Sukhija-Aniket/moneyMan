"""replace needs_review boolean with review_status enum

Revision ID: 65173cd2f933
Revises: 3a80ae28526e
Create Date: 2026-08-09 18:47:30.245390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65173cd2f933'
down_revision: Union[str, Sequence[str], None] = '3a80ae28526e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transactions', sa.Column('review_status', sa.String(), nullable=True))

    # Backfill from the boolean this column replaces: rows a human hasn't looked at yet
    # (needs_review=true) become "pending"; everything else defaults to "confirmed" — the
    # not_transaction/duplicate statuses only ever get set later by an explicit human action,
    # never assigned retroactively here.
    op.execute("UPDATE transactions SET review_status = CASE WHEN needs_review THEN 'pending' ELSE 'confirmed' END")

    op.alter_column('transactions', 'review_status', nullable=False)
    op.create_check_constraint(
        'ck_transactions_review_status',
        'transactions',
        "review_status IN ('pending', 'confirmed', 'not_transaction', 'duplicate')",
    )
    op.drop_index(op.f('ix_transactions_needs_review'), table_name='transactions')
    op.create_index(op.f('ix_transactions_review_status'), 'transactions', ['review_status'], unique=False)
    op.drop_column('transactions', 'needs_review')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('transactions', sa.Column('needs_review', sa.BOOLEAN(), nullable=True))
    op.execute("UPDATE transactions SET needs_review = (review_status = 'pending')")
    op.alter_column('transactions', 'needs_review', nullable=False)

    op.drop_index(op.f('ix_transactions_review_status'), table_name='transactions')
    op.create_index(op.f('ix_transactions_needs_review'), 'transactions', ['needs_review'], unique=False)
    op.drop_constraint('ck_transactions_review_status', 'transactions', type_='check')
    op.drop_column('transactions', 'review_status')
