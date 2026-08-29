"""merge accounts by last4 only

Revision ID: 29aa5caf0b36
Revises: eefbcaf9ffb3
Create Date: 2026-08-17 00:00:00.000000

Merges duplicate `accounts` rows that share the same (user_id, last4) but differ in
issuer_name/account_type — both LLM-extracted and inconsistent across emails for the same
real account (e.g. "Axis Bank" vs "Axis Bank Ltd."). For each (user_id, last4) group with
last4 IS NOT NULL, keeps the oldest row as canonical, reassigns all transactions from the
other rows to it, then deletes the redundant rows. Rows with last4 IS NULL are left as-is
(grouping falls back to issuer_name alone for those — see _get_or_create_account).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29aa5caf0b36'
down_revision: Union[str, Sequence[str], None] = 'eefbcaf9ffb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # Reassign transactions from every non-canonical account to the oldest account in its
    # (user_id, last4) group, then delete the now-orphaned duplicate accounts.
    conn.execute(
        sa.text(
            """
            WITH canonical AS (
                SELECT DISTINCT ON (user_id, last4) id, user_id, last4
                FROM accounts
                WHERE last4 IS NOT NULL
                ORDER BY user_id, last4, created_at ASC
            )
            UPDATE transactions t
            SET account_id = c.id
            FROM accounts a
            JOIN canonical c ON c.user_id = a.user_id AND c.last4 = a.last4
            WHERE t.account_id = a.id AND a.id != c.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH canonical AS (
                SELECT DISTINCT ON (user_id, last4) id, user_id, last4
                FROM accounts
                WHERE last4 IS NOT NULL
                ORDER BY user_id, last4, created_at ASC
            )
            DELETE FROM accounts a
            USING canonical c
            WHERE a.user_id = c.user_id AND a.last4 = c.last4 AND a.id != c.id
            """
        )
    )

    op.drop_constraint('uq_accounts_user_issuer_last4_type', 'accounts', type_='unique')
    op.create_unique_constraint('uq_accounts_user_last4', 'accounts', ['user_id', 'last4'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_accounts_user_last4', 'accounts', type_='unique')
    op.create_unique_constraint(
        'uq_accounts_user_issuer_last4_type', 'accounts', ['user_id', 'issuer_name', 'last4', 'account_type']
    )
    # Merged accounts/reassigned transactions are not un-merged on downgrade — that data
    # loss (which issuer_name/account_type a given transaction's account originally had) is
    # not reversible from the schema alone.
