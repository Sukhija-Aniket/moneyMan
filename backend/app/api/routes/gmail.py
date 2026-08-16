import uuid
from datetime import date, timedelta

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
from app.schemas.gmail import GmailStatus, GmailSyncRequest, GmailSyncResult, GmailSyncTriggerOut
from app.services import sync_trigger_service
from app.services.sync_job_publisher import publish_sync_job

router = APIRouter(prefix="/gmail", tags=["gmail"])
settings = get_settings()

MAX_SYNC_RANGE_DAYS = 92  # ~3 months


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
    if (date_to - date_from) > timedelta(days=MAX_SYNC_RANGE_DAYS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date range cannot exceed {MAX_SYNC_RANGE_DAYS} days (~3 months).",
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


@router.post("/sync/range", response_model=GmailSyncTriggerOut, status_code=status.HTTP_202_ACCEPTED)
async def sync_range(
    sync_request: GmailSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GmailSyncTriggerOut:
    """Starts an async range sync: validates the range, rejects if an overlapping range for
    this user is already in progress, records a sync_triggers row, and publishes a job for
    the worker to process. Returns immediately — poll GET /gmail/sync/triggers/{id} for status."""
    if sync_request.date_from is None or sync_request.date_to is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from and date_to are required for a range sync.",
        )
    _validate_sync_range(sync_request.date_from, sync_request.date_to, current_user.timezone)

    overlapping = await sync_trigger_service.find_overlapping_in_progress(
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

    trigger = await sync_trigger_service.create_trigger(
        db, current_user.id, sync_request.date_from, sync_request.date_to
    )

    publish_sync_job(
        GmailSyncJob(
            trigger_id=str(trigger.id),
            user_id=str(current_user.id),
            date_from=sync_request.date_from.isoformat(),
            date_to=sync_request.date_to.isoformat(),
        )
    )

    return trigger


@router.get("/sync/triggers/{trigger_id}", response_model=GmailSyncTriggerOut)
async def get_sync_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GmailSyncTriggerOut:
    trigger = await sync_trigger_service.get_trigger(db, current_user.id, uuid.UUID(trigger_id))
    if trigger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync trigger not found.")
    return trigger


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
