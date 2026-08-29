import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from moneyman_shared.db.base import Base

# Shared (not backend-only) because Worker 1's fetch stage reads this directly to decide
# whether it can skip calling the Gmail API at all for a given date range — a range only
# needs its raw_emails listed/fetched from Gmail ONCE, regardless of how many times
# extraction on those emails later needs to be retried. Rows are inserted the moment a
# segment's fetch (list + Gate 1 + raw_emails write) completes, independent of whether
# every candidate's later classification/extraction succeeds — that stronger condition is
# what synced_ranges (backend-owned) tracks instead. Merge-inserted the same way as
# synced_ranges (see shared/services/coverage.py) — gap computation is correct against an
# unmerged row set too, so merging is a maintenance optimization, not a correctness
# requirement.


class FetchedRange(Base):
    __tablename__ = "fetched_ranges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
