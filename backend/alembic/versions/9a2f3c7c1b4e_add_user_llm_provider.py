"""add user llm_provider

Revision ID: 9a2f3c7c1b4e
Revises: 7944e569bb15
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a2f3c7c1b4e'
down_revision: Union[str, Sequence[str], None] = '7944e569bb15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('llm_provider', sa.String(), nullable=False, server_default='anthropic'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'llm_provider')
