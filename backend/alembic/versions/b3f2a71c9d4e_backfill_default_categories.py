"""backfill default categories for existing users

Revision ID: b3f2a71c9d4e
Revises: 29aa5caf0b36
Create Date: 2026-08-28 00:00:00.000000

One-time backfill: inserts the standard default category set (see
moneyman_shared.services.default_categories.DEFAULT_CATEGORY_NAMES) for every user who
doesn't already have it, so existing users (created before default-category seeding was
added to the signup flow in app/api/routes/auth.py) get the same categories a new
signup would. Uses ON CONFLICT DO NOTHING against the existing uq_categories_user_name
constraint so it's safe to re-run and won't clobber a category a user already created
with a matching name.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f2a71c9d4e'
down_revision: Union[str, Sequence[str], None] = '29aa5caf0b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_CATEGORY_NAMES = [
    "General",
    "Food",
    "Groceries",
    "Travel",
    "Transport",
    "Medicines",
    "Health",
    "Shopping",
    "Bills & Utilities",
    "Entertainment",
    "Rent",
    "Education",
    "Income",
    "Transfer",
]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    for name in DEFAULT_CATEGORY_NAMES:
        conn.execute(
            sa.text(
                """
                INSERT INTO categories (id, user_id, name, is_system, created_at, updated_at)
                SELECT gen_random_uuid(), u.id, :name, true, now(), now()
                FROM users u
                ON CONFLICT (user_id, name) DO NOTHING
                """
            ),
            {"name": name},
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM categories WHERE is_system = true AND name = ANY(:names)"
        ),
        {"names": DEFAULT_CATEGORY_NAMES},
    )
