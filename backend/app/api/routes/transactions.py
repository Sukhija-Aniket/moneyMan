import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.transaction import TransactionListResponse, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _apply_filters(
    stmt,
    date_from: date | None,
    date_to: date | None,
    category_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
    txn_type: str | None,
    amount_min: float | None,
    amount_max: float | None,
    search: str | None,
    needs_review: bool | None,
):
    if date_from is not None:
        stmt = stmt.where(Transaction.txn_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.txn_date <= date_to)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if txn_type is not None:
        stmt = stmt.where(Transaction.txn_type == txn_type)
    if amount_min is not None:
        stmt = stmt.where(Transaction.amount >= amount_min)
    if amount_max is not None:
        stmt = stmt.where(Transaction.amount <= amount_max)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Transaction.merchant_normalized.ilike(pattern))
    if needs_review is not None:
        stmt = stmt.where(Transaction.needs_review == needs_review)
    return stmt


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    txn_type: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    search: str | None = None,
    needs_review: bool | None = None,
    limit: int = Query(default=50, le=200, ge=1),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    base_stmt = select(Transaction).where(Transaction.user_id == current_user.id)
    base_stmt = _apply_filters(
        base_stmt, date_from, date_to, category_id, account_id, txn_type, amount_min, amount_max, search, needs_review
    )

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        base_stmt.options(selectinload(Transaction.category), selectinload(Transaction.account))
        .order_by(Transaction.txn_date.desc().nullslast(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    return TransactionListResponse(
        items=[TransactionOut.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _get_owned_transaction(db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.category), selectinload(Transaction.account))
        .where(Transaction.user_id == user_id, Transaction.id == transaction_id)
    )
    result = await db.execute(stmt)
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    transaction = await _get_owned_transaction(db, current_user.id, transaction_id)
    return TransactionOut.model_validate(transaction)


@router.patch("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    transaction = await _get_owned_transaction(db, current_user.id, transaction_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(transaction, field, value)

    await db.commit()
    await db.refresh(transaction, attribute_names=["category", "account"])
    return TransactionOut.model_validate(transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    transaction = await _get_owned_transaction(db, current_user.id, transaction_id)
    await db.delete(transaction)
    await db.commit()
