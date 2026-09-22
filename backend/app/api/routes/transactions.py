import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from moneyman_shared.db.models.raw_email import RawEmail

from moneyman_shared.db.models.review_status import ReviewStatus
from moneyman_shared.db.models.transaction import Transaction
from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import get_db
from moneyman_shared.services.gmail_sync import create_manual_transaction
from app.deps import get_current_user
from app.schemas.transaction import (
    RawEmailOut,
    TransactionCreate,
    TransactionListResponse,
    TransactionOut,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _transaction_out(transaction: Transaction) -> TransactionOut:
    """raw_email is only ever eager-loaded for its gmail_message_id (shown in the table for
    spotting duplicates) — the full body is fetched separately, on demand, via
    GET /transactions/{id}/raw-email, since embedding it here would ship every row's full
    email body on every list/update response."""
    out = TransactionOut.model_validate(transaction)
    out.raw_email_gmail_message_id = (
        transaction.raw_email.gmail_message_id if transaction.raw_email is not None else None
    )
    return out


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
    review_status: ReviewStatus | None,
    include_dismissed: bool,
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
    if review_status is not None:
        stmt = stmt.where(Transaction.review_status == review_status)
    elif not include_dismissed:
        stmt = stmt.where(Transaction.review_status.not_in(["not_transaction", "duplicate"]))
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
    review_status: ReviewStatus | None = None,
    include_dismissed: bool = False,
    limit: int = Query(default=50, le=200, ge=1),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    base_stmt = select(Transaction).where(Transaction.user_id == current_user.id)
    base_stmt = _apply_filters(
        base_stmt,
        date_from,
        date_to,
        category_id,
        account_id,
        txn_type,
        amount_min,
        amount_max,
        search,
        review_status,
        include_dismissed,
    )

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        base_stmt.options(
            selectinload(Transaction.category),
            selectinload(Transaction.account),
            selectinload(Transaction.raw_email).load_only(RawEmail.id, RawEmail.gmail_message_id),
        )
        .order_by(Transaction.txn_date.desc().nullslast(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    return TransactionListResponse(
        items=[_transaction_out(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/manual", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction_route(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    """For a transaction with no backing email (rare — e.g. cash, or a bank that never sent
    a notification). Builds a synthetic email from the given fields and runs it through the
    real extraction pipeline (see create_manual_transaction) rather than writing the
    Transaction directly, so account matching/duplicate detection stay on one code path."""
    try:
        transaction = await create_manual_transaction(
            db,
            current_user,
            txn_type=payload.txn_type,
            amount=float(payload.amount),
            currency=payload.currency,
            account_id=payload.account_id,
            txn_date=payload.txn_date,
            merchant=payload.merchant,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return await get_transaction(transaction.id, current_user, db)


async def _get_owned_transaction(db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
    stmt = (
        select(Transaction)
        .options(
            selectinload(Transaction.category),
            selectinload(Transaction.account),
            selectinload(Transaction.raw_email).load_only(RawEmail.id, RawEmail.gmail_message_id),
        )
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
    return _transaction_out(transaction)


@router.get("/{transaction_id}/raw-email", response_model=RawEmailOut)
async def get_transaction_raw_email(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RawEmailOut:
    """Fetched on demand ("View raw") rather than embedded in the list/get transaction
    responses — the full email body can be many KB and most rows are never opened."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.raw_email))
        .where(Transaction.user_id == current_user.id, Transaction.id == transaction_id)
    )
    result = await db.execute(stmt)
    transaction = result.scalar_one_or_none()
    if transaction is None or transaction.raw_email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw email not found")
    return RawEmailOut.model_validate(transaction.raw_email)


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
    if "review_status" in update_data:
        transaction.reviewed_by = "human"

    await db.commit()
    await db.refresh(transaction, attribute_names=["category", "account", "raw_email"])
    return _transaction_out(transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    transaction = await _get_owned_transaction(db, current_user.id, transaction_id)
    await db.delete(transaction)
    await db.commit()
