import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.sync_request import SyncRequest
from app.db.models.sync_segment import SyncSegment

# Backend-owned: only the backend writes sync_requests/sync_segments. Workers never touch
# these tables — they only publish events (see app/services/sync_fetch_events_consumer.py) —
# which keeps the "is a sync already in progress" overlap check below free of any race
# against a worker-side write.


async def find_overlapping_in_progress_segment(
    db: AsyncSession, user_id: uuid.UUID, date_from: date, date_to: date
) -> SyncSegment | None:
    """Two ranges [a1,b1] and [a2,b2] overlap iff a1 <= b2 and a2 <= b1."""
    stmt = select(SyncSegment).where(
        SyncSegment.user_id == user_id,
        SyncSegment.status == "in_progress",
        SyncSegment.date_from <= date_to,
        SyncSegment.date_to >= date_from,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_request_with_segments(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
    gaps: list[tuple[date, date]],
) -> SyncRequest:
    """Creates the parent sync_requests row plus one sync_segments row per gap. An empty
    `gaps` list (the whole requested range was already covered) creates the parent directly
    with status="success" and no children."""
    request = SyncRequest(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        status="success" if not gaps else "in_progress",
    )
    db.add(request)
    await db.flush()

    for gap_from, gap_to in gaps:
        db.add(
            SyncSegment(
                sync_request_id=request.id,
                user_id=user_id,
                date_from=gap_from,
                date_to=gap_to,
                status="in_progress",
            )
        )

    await db.commit()
    await db.refresh(request, attribute_names=["segments"])
    return request


async def get_request(db: AsyncSession, user_id: uuid.UUID, request_id: uuid.UUID) -> SyncRequest | None:
    result = await db.execute(
        select(SyncRequest).where(SyncRequest.id == request_id, SyncRequest.user_id == user_id)
    )
    request = result.scalar_one_or_none()
    if request is None:
        return None
    await db.refresh(request, attribute_names=["segments"])
    return request


async def list_requests(
    db: AsyncSession, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[SyncRequest], int]:
    """Sync history for the "Sync a date range" page — every request the user has ever
    triggered (in progress, succeeded, partially failed, or failed), newest first."""
    total = (
        await db.execute(
            select(func.count()).select_from(SyncRequest).where(SyncRequest.user_id == user_id)
        )
    ).scalar_one()

    stmt = (
        select(SyncRequest)
        .options(selectinload(SyncRequest.segments))
        .where(SyncRequest.user_id == user_id)
        .order_by(SyncRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_current_in_progress(db: AsyncSession, user_id: uuid.UUID) -> SyncSegment | None:
    result = await db.execute(
        select(SyncSegment)
        .where(SyncSegment.user_id == user_id, SyncSegment.status == "in_progress")
        .order_by(SyncSegment.started_at.asc())
    )
    return result.scalars().first()


async def get_segment_by_id(db: AsyncSession, segment_id: uuid.UUID) -> SyncSegment | None:
    result = await db.execute(select(SyncSegment).where(SyncSegment.id == segment_id))
    return result.scalar_one_or_none()


async def mark_segment_terminal(
    db: AsyncSession,
    segment_id: uuid.UUID,
    status: str,
    error: str | None = None,
    total_candidates: int | None = None,
    processed_candidates: int | None = None,
) -> SyncSegment | None:
    segment = await get_segment_by_id(db, segment_id)
    if segment is None:
        return None
    segment.status = status
    segment.error = error
    if total_candidates is not None:
        segment.total_candidates = total_candidates
    if processed_candidates is not None:
        segment.processed_candidates = processed_candidates
    segment.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return segment


async def maybe_finalize_request(db: AsyncSession, sync_request_id: uuid.UUID) -> None:
    """Derives and sets sync_requests.status from its children once every segment is
    terminal (status != "in_progress"): "success" if every segment reached
    "extraction_complete", "failed" if every segment ended in "failed" (fetch itself never
    succeeded for any of them), "partial_failure" otherwise — which covers both a genuine
    mix of segment outcomes and the "fetch succeeded but some emails still need
    reclassification" case ("extraction_failed"). Leaves status untouched (still
    "in_progress") while any segment remains in_progress."""
    result = await db.execute(select(SyncRequest).where(SyncRequest.id == sync_request_id))
    request = result.scalar_one_or_none()
    if request is None:
        return

    seg_result = await db.execute(select(SyncSegment).where(SyncSegment.sync_request_id == sync_request_id))
    segments = seg_result.scalars().all()
    if not segments or any(s.status == "in_progress" for s in segments):
        return

    succeeded = sum(1 for s in segments if s.status == "extraction_complete")
    all_failed = all(s.status == "failed" for s in segments)
    if succeeded == len(segments):
        request.status = "success"
    elif all_failed:
        request.status = "failed"
    else:
        request.status = "partial_failure"

    await db.commit()
