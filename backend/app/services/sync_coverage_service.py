import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.synced_range import SyncedRange
from moneyman_shared.services.coverage import compute_gaps, get_covered_ranges, merge_insert_range

# Thin backend-facing wrapper over moneyman_shared.services.coverage, fixed to the
# SyncedRange model — i.e. "has this range been FULLY synced" (fetch AND extraction both
# done). Worker 1 uses the same underlying coverage module directly against FetchedRange for
# its own "do I even need to call Gmail" check (see worker/fetch_stage.py) — the two are
# deliberately independent tables/checks, not layered on top of each other.


async def get_synced_ranges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[date, date]]:
    return await get_covered_ranges(db, SyncedRange, user_id)


async def merge_insert_synced_range(db: AsyncSession, user_id: uuid.UUID, date_from: date, date_to: date) -> None:
    await merge_insert_range(db, SyncedRange, user_id, date_from, date_to)


__all__ = ["compute_gaps", "get_synced_ranges", "merge_insert_synced_range"]
