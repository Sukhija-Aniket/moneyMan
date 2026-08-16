from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import get_db
from app.deps import get_current_user
from app.schemas.summary import (
    AccountSummaryItem,
    BankSummaryItem,
    CategorySummaryItem,
    OverviewSummary,
    TrendPoint,
)
from app.services import aggregation_service
from moneyman_shared.services.user_time import today_for_user

router = APIRouter(prefix="/summary", tags=["summary"])


def _validate_date_range(date_from: date | None, date_to: date | None, user_timezone: str) -> None:
    today = today_for_user(user_timezone)

    if date_from is not None and date_from > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_from ({date_from.isoformat()}) cannot be in the future.",
        )
    if date_to is not None and date_to > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_to ({date_to.isoformat()}) cannot be in the future.",
        )
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_from ({date_from.isoformat()}) cannot be after date_to ({date_to.isoformat()}).",
        )


@router.get("/overview", response_model=OverviewSummary)
async def summary_overview(
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OverviewSummary:
    _validate_date_range(date_from, date_to, current_user.timezone)
    data = await aggregation_service.get_overview(db, current_user.id, date_from, date_to)
    return OverviewSummary(**data)


@router.get("/by-category", response_model=list[CategorySummaryItem])
async def summary_by_category(
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategorySummaryItem]:
    _validate_date_range(date_from, date_to, current_user.timezone)
    data = await aggregation_service.get_by_category(db, current_user.id, date_from, date_to)
    return [CategorySummaryItem(**row) for row in data]


@router.get("/by-account", response_model=list[AccountSummaryItem])
async def summary_by_account(
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AccountSummaryItem]:
    _validate_date_range(date_from, date_to, current_user.timezone)
    data = await aggregation_service.get_by_account(db, current_user.id, date_from, date_to)
    return [AccountSummaryItem(**row) for row in data]


@router.get("/by-bank", response_model=list[BankSummaryItem])
async def summary_by_bank(
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BankSummaryItem]:
    _validate_date_range(date_from, date_to, current_user.timezone)
    data = await aggregation_service.get_by_bank(db, current_user.id, date_from, date_to)
    return [BankSummaryItem(**row) for row in data]


@router.get("/trends", response_model=list[TrendPoint])
async def summary_trends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrendPoint]:
    data = await aggregation_service.get_trends(db, current_user.id)
    return [TrendPoint(**row) for row in data]
