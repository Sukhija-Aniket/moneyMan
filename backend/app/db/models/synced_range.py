import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from moneyman_shared.db.base import Base

# Backend-owned: coverage ledger of date ranges that have been FULLY synced for a user (every
# candidate email in the range reached a terminal extraction outcome). Rows are inserted only
# when a sync_segments row succeeds, and are merge-inserted (see sync_coverage_service) rather
# than accumulated as many small disjoint rows — but gap computation is correct against an
# unmerged row set too, so a merge is a maintenance optimization, not a correctness requirement.


class SyncedRange(Base):
    __tablename__ = "synced_ranges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
