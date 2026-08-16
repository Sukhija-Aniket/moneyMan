import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.config import get_settings
from moneyman_shared.db.models.oauth_token import OAuthToken
from moneyman_shared.db.models.raw_email import RawEmail
from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import get_db
from moneyman_shared.messaging.schemas import GmailSyncJob
from moneyman_shared.services.gmail_sync import GmailSyncError, run_gmail_sync
from moneyman_shared.services.user_time import today_for_user
from app.deps import get_current_user
from app.schemas.gmail import CurrentSyncOut, GmailStatus, GmailSyncRequest, GmailSyncResult, SyncRequestOut
from app.services import sync_coverage_service, sync_request_service
from app.services.sync_job_publisher import publish_sync_job

router = APIRouter(prefix="/gmail", tags=["gmail"])
settings = get_settings()

MAX_SYNC_RANGE_DAYS = 90
MIN_SYNC_RANGE_DAYS = 1  # a request must span at least one full day


def _validate_sync_range(date_from: date | None, date_to: date | None, user_timezone: str) -> None:
    if date_from is None and date_to is None:
        return

    if date_from is None or date_to is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from and date_to must both be provided together.",
        )

    today = today_for_user(user_timezone)

    if date_from > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_from ({date_from.isoformat()}) cannot be in the future.",
        )
    if date_to > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_to ({date_to.isoformat()}) cannot be in the future.",
        )
    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_from ({date_from.isoformat()}) cannot be after date_to ({date_to.isoformat()}).",
        )
    span_days = (date_to - date_from).days + 1  # inclusive of both endpoints
    if span_days < MIN_SYNC_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date range must span at least {MIN_SYNC_RANGE_DAYS} day.",
        )
    if span_days > MAX_SYNC_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date range cannot exceed {MAX_SYNC_RANGE_DAYS} days.",
        )


@router.post("/sync", response_model=GmailSyncResult)
async def sync_now(
    sync_request: GmailSyncRequest = GmailSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GmailSyncResult:
    """Plain sync (no date range): runs synchronously and returns the result — bounded to
    GMAIL_SYNC_MAX_RESULTS messages, so this stays fast. For a date range, use
    POST /gmail/sync/range instead, which runs asynchronously via the worker."""
    _validate_sync_range(sync_request.date_from, sync_request.date_to, current_user.timezone)

    try:
        counters = await run_gmail_sync(db, current_user, sync_request.date_from, sync_request.date_to)
    except GmailSyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return GmailSyncResult(**counters.as_dict())


@router.post("/sync/range", response_model=SyncRequestOut, status_code=status.HTTP_202_ACCEPTED)
async def sync_range(
    sync_request: GmailSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncRequestOut:
    """Starts an async range sync. Validates the range, rejects (409) if an overlapping
    range for this user is already in progress, computes which sub-ranges aren't already
    covered by synced_ranges, and publishes one job per gap segment for the worker to
    process. Returns immediately — poll GET /gmail/sync/requests/{id} for status."""
    if sync_request.date_from is None or sync_request.date_to is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from and date_to are required for a range sync.",
        )
    _validate_sync_range(sync_request.date_from, sync_request.date_to, current_user.timezone)

    overlapping = await sync_request_service.find_overlapping_in_progress_segment(
        db, current_user.id, sync_request.date_from, sync_request.date_to
    )
    if overlapping is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A sync for an overlapping range ({overlapping.date_from} to {overlapping.date_to}) "
                "is already in progress."
            ),
        )

    synced = await sync_coverage_service.get_synced_ranges(db, current_user.id)
    gaps = sync_coverage_service.compute_gaps(synced, sync_request.date_from, sync_request.date_to)

    request = await sync_request_service.create_request_with_segments(
        db, current_user.id, sync_request.date_from, sync_request.date_to, gaps
    )

    for segment in request.segments:
        publish_sync_job(
            GmailSyncJob(
                segment_id=str(segment.id),
                user_id=str(current_user.id),
                date_from=segment.date_from.isoformat() if segment.date_from else None,
                date_to=segment.date_to.isoformat() if segment.date_to else None,
            )
        )

    return request


@router.get("/sync/requests/{request_id}", response_model=SyncRequestOut)
async def get_sync_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncRequestOut:
    request = await sync_request_service.get_request(db, current_user.id, uuid.UUID(request_id))
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync request not found.")
    return request


@router.get("/sync/current", response_model=CurrentSyncOut)
async def get_current_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentSyncOut:
    segment = await sync_request_service.get_current_in_progress(db, current_user.id)
    if segment is None:
        return CurrentSyncOut(in_progress=False)
    return CurrentSyncOut(
        in_progress=True, segment_id=segment.id, date_from=segment.date_from, date_to=segment.date_to
    )


@router.get("/status", response_model=GmailStatus)
async def gmail_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GmailStatus:
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == current_user.id))
    token = result.scalar_one_or_none()
    if token is None:
        return GmailStatus(connected=False)

    range_result = await db.execute(
        select(func.min(RawEmail.received_at), func.max(RawEmail.received_at)).where(
            RawEmail.user_id == current_user.id
        )
    )
    earliest, latest = range_result.one()

    return GmailStatus(
        connected=True,
        scope=token.scope,
        token_expiry=token.token_expiry.isoformat() if token.token_expiry else None,
        earliest_synced_at=earliest.isoformat() if earliest else None,
        latest_synced_at=latest.isoformat() if latest else None,
    )


@router.post("/disconnect")
async def gmail_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == current_user.id))
    token = result.scalar_one_or_none()
    if token is not None:
        await db.delete(token)
        await db.commit()
    return {"status": "disconnected"}
