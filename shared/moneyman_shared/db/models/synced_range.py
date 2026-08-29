import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from moneyman_shared.db.base import Base

# Coverage ledger of date ranges FULLY synced for a user — i.e. every candidate email in the
# range reached a genuine verdict (extracted or not_transaction), not just a terminal outcome
# (classify_failed/extract_failed are terminal but not genuine verdicts — see
# moneyman_shared.services.gmail_sync.extract_one_email). Only the backend writes rows here
# (on a segment's status="extraction_complete"), but the model lives in shared alongside
# fetched_ranges since both use the same generic coverage/gap-computation logic
# (moneyman_shared.services.coverage). See fetched_range.py for the weaker "fetch alone
# done" coverage this table is NOT tracking.


class SyncedRange(Base):
    __tablename__ = "synced_ranges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
