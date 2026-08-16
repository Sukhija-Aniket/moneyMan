import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sync_trigger import SyncTrigger

# Only the backend writes sync_triggers — the worker signals completion via a Pulsar event
# that the backend consumes and applies here. This keeps a single writer for "is this range
# currently syncing," so the overlap check below can't race with a worker-side write.


async def find_overlapping_in_progress(
    db: AsyncSession, user_id: uuid.UUID, date_from: date, date_to: date
) -> SyncTrigger | None:
    """Two ranges [a1,b1] and [a2,b2] overlap iff a1 <= b2 and a2 <= b1."""
    stmt = select(SyncTrigger).where(
        SyncTrigger.user_id == user_id,
        SyncTrigger.status == "in_progress",
        SyncTrigger.date_from <= date_to,
        SyncTrigger.date_to >= date_from,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_trigger(db: AsyncSession, user_id: uuid.UUID, date_from: date, date_to: date) -> SyncTrigger:
    trigger = SyncTrigger(user_id=user_id, date_from=date_from, date_to=date_to, status="in_progress")
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return trigger


async def get_trigger(db: AsyncSession, user_id: uuid.UUID, trigger_id: uuid.UUID) -> SyncTrigger | None:
    result = await db.execute(
        select(SyncTrigger).where(SyncTrigger.id == trigger_id, SyncTrigger.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def mark_completed(
    db: AsyncSession, trigger_id: uuid.UUID, status: str, error: str | None = None
) -> None:
    result = await db.execute(select(SyncTrigger).where(SyncTrigger.id == trigger_id))
    trigger = result.scalar_one_or_none()
    if trigger is None:
        return
    trigger.status = status
    trigger.error = error
    trigger.completed_at = datetime.now(timezone.utc)
    await db.commit()
