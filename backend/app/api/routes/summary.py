from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.summary import (
    AccountSummaryItem,
    BankSummaryItem,
    CategorySummaryItem,
    OverviewSummary,
    TrendPoint,
)
from app.services import aggregation_service

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/overview", response_model=OverviewSummary)
async def summary_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OverviewSummary:
    data = await aggregation_service.get_overview(db, current_user.id)
    return OverviewSummary(**data)


@router.get("/by-category", response_model=list[CategorySummaryItem])
async def summary_by_category(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategorySummaryItem]:
    data = await aggregation_service.get_by_category(db, current_user.id)
    return [CategorySummaryItem(**row) for row in data]


@router.get("/by-account", response_model=list[AccountSummaryItem])
async def summary_by_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AccountSummaryItem]:
    data = await aggregation_service.get_by_account(db, current_user.id)
    return [AccountSummaryItem(**row) for row in data]


@router.get("/by-bank", response_model=list[BankSummaryItem])
async def summary_by_bank(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BankSummaryItem]:
    data = await aggregation_service.get_by_bank(db, current_user.id)
    return [BankSummaryItem(**row) for row in data]


@router.get("/trends", response_model=list[TrendPoint])
async def summary_trends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrendPoint]:
    data = await aggregation_service.get_trends(db, current_user.id)
    return [TrendPoint(**row) for row in data]
