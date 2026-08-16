import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.account import Account
from moneyman_shared.db.models.category import Category
from moneyman_shared.db.models.transaction import Transaction

_DISMISSED_STATUSES = ("not_transaction", "duplicate")


async def get_overview(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    stmt = select(
        func.coalesce(
            func.sum(Transaction.amount).filter(Transaction.txn_type == "credit"), 0
        ).label("total_income"),
        func.coalesce(
            func.sum(Transaction.amount).filter(Transaction.txn_type == "debit"), 0
        ).label("total_spend"),
        func.count(Transaction.id).label("transaction_count"),
        func.count(Transaction.id).filter(Transaction.review_status == "pending").label("needs_review_count"),
    ).where(Transaction.user_id == user_id, Transaction.review_status.not_in(_DISMISSED_STATUSES))

    if date_from is not None:
        stmt = stmt.where(Transaction.txn_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.txn_date <= date_to)

    result = (await db.execute(stmt)).one()

    total_income = result.total_income or 0
    total_spend = result.total_spend or 0

    return {
        "total_income": total_income,
        "total_spend": total_spend,
        "net": total_income - total_spend,
        "transaction_count": result.transaction_count,
        "needs_review_count": result.needs_review_count,
        "currency": "USD",
    }


async def get_by_category(
    db: AsyncSession, user_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    stmt = (
        select(
            Category.id,
            Category.name,
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .select_from(Transaction)
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .where(Transaction.user_id == user_id, Transaction.review_status.not_in(_DISMISSED_STATUSES))
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.txn_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.txn_date <= date_to)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "category_id": row.id,
            "category_name": row.name or "Uncategorized",
            "total_amount": row.total_amount,
            "transaction_count": row.transaction_count,
        }
        for row in rows
    ]


async def get_by_account(
    db: AsyncSession, user_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    stmt = (
        select(
            Account.id,
            Account.display_name,
            Account.issuer_name,
            Account.last4,
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .select_from(Transaction)
        .join(Account, Transaction.account_id == Account.id, isouter=True)
        .where(Transaction.user_id == user_id, Transaction.review_status.not_in(_DISMISSED_STATUSES))
        .group_by(Account.id, Account.display_name, Account.issuer_name, Account.last4)
        .order_by(func.sum(Transaction.amount).desc())
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.txn_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.txn_date <= date_to)

    rows = (await db.execute(stmt)).all()
    results = []
    for row in rows:
        name = row.display_name
        if not name:
            parts = [p for p in [row.issuer_name, row.last4] if p]
            name = " ".join(parts) if parts else "Unknown account"
        results.append(
            {
                "account_id": row.id,
                "display_name": name,
                "total_amount": row.total_amount,
                "transaction_count": row.transaction_count,
            }
        )
    return results


async def get_by_bank(
    db: AsyncSession, user_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    stmt = (
        select(
            func.coalesce(Account.issuer_name, "Unknown").label("issuer_name"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .select_from(Transaction)
        .join(Account, Transaction.account_id == Account.id, isouter=True)
        .where(Transaction.user_id == user_id, Transaction.review_status.not_in(_DISMISSED_STATUSES))
        .group_by(Account.issuer_name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.txn_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.txn_date <= date_to)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "issuer_name": row.issuer_name,
            "total_amount": row.total_amount,
            "transaction_count": row.transaction_count,
        }
        for row in rows
    ]


async def get_trends(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    period = func.to_char(Transaction.txn_date, "YYYY-MM")
    stmt = (
        select(
            period.label("period"),
            func.coalesce(
                func.sum(Transaction.amount).filter(Transaction.txn_type == "credit"), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(Transaction.amount).filter(Transaction.txn_type == "debit"), 0
            ).label("total_spend"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.txn_date.is_not(None),
            Transaction.review_status.not_in(_DISMISSED_STATUSES),
        )
        .group_by(period)
        .order_by(period)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "period": row.period,
            "total_income": row.total_income,
            "total_spend": row.total_spend,
            "transaction_count": row.transaction_count,
        }
        for row in rows
    ]
