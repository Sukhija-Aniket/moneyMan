"""replace sync_triggers with sync_requests/sync_segments/synced_ranges

Revision ID: 23a746d82862
Revises: 65173cd2f933
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23a746d82862'
down_revision: Union[str, Sequence[str], None] = '65173cd2f933'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_sync_triggers_user_id'), table_name='sync_triggers')
    op.drop_table('sync_triggers')

    op.create_table(
        'sync_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sync_requests_user_id'), 'sync_requests', ['user_id'], unique=False)

    op.create_table(
        'sync_segments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sync_request_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('total_candidates', sa.Integer(), nullable=True),
        sa.Column('processed_candidates', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['sync_request_id'], ['sync_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sync_segments_sync_request_id'), 'sync_segments', ['sync_request_id'], unique=False)
    op.create_index(op.f('ix_sync_segments_user_id'), 'sync_segments', ['user_id'], unique=False)

    op.create_table(
        'synced_ranges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_synced_ranges_user_id'), 'synced_ranges', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_synced_ranges_user_id'), table_name='synced_ranges')
    op.drop_table('synced_ranges')

    op.drop_index(op.f('ix_sync_segments_user_id'), table_name='sync_segments')
    op.drop_index(op.f('ix_sync_segments_sync_request_id'), table_name='sync_segments')
    op.drop_table('sync_segments')

    op.drop_index(op.f('ix_sync_requests_user_id'), table_name='sync_requests')
    op.drop_table('sync_requests')

    op.create_table(
        'sync_triggers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sync_triggers_user_id'), 'sync_triggers', ['user_id'], unique=False)
