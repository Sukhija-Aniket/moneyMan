"""add txn_type to categories

Revision ID: ddec1c5b04d7
Revises: c4a91e2f7b8d
Create Date: 2026-08-30 00:00:00.000000

Categories are now tied to a transaction direction (debit or credit) so the category
dropdown on a transaction row can be restricted to categories that make sense for that
row's txn_type (a credit shouldn't be filed under "Groceries", a debit shouldn't be
filed under "Income"). Backfills every existing category to 'debit' except "Income" and
"Returns", which are 'credit' -- self_transfer transactions have no associated category
type since they're excluded from category dropdowns entirely (handled in application
code, not here).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddec1c5b04d7'
down_revision: Union[str, Sequence[str], None] = 'c4a91e2f7b8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CREDIT_CATEGORY_NAMES = ["Income", "Returns"]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("categories", sa.Column("txn_type", sa.String(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE categories SET txn_type = 'credit' WHERE name = ANY(:names)"),
        {"names": CREDIT_CATEGORY_NAMES},
    )
    conn.execute(sa.text("UPDATE categories SET txn_type = 'debit' WHERE txn_type IS NULL"))

    op.alter_column("categories", "txn_type", nullable=False)
    op.create_check_constraint(
        "ck_categories_txn_type",
        "categories",
        "txn_type IN ('debit', 'credit')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_categories_txn_type", "categories", type_="check")
    op.drop_column("categories", "txn_type")
