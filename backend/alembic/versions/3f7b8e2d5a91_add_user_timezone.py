"""add user timezone

Revision ID: 3f7b8e2d5a91
Revises: 9a2f3c7c1b4e
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3f7b8e2d5a91'
down_revision: Union[str, Sequence[str], None] = '9a2f3c7c1b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'timezone')
