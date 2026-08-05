import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.session import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/transactions.csv")
async def export_transactions_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.category), selectinload(Transaction.account))
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.txn_date.desc().nullslast())
    )
    result = await db.execute(stmt)
    transactions = result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "date",
            "amount",
            "currency",
            "type",
            "merchant",
            "category",
            "account",
            "needs_review",
            "confidence",
        ]
    )
    for txn in transactions:
        writer.writerow(
            [
                txn.txn_date.isoformat() if txn.txn_date else "",
                txn.amount,
                txn.currency,
                txn.txn_type,
                txn.merchant_normalized or txn.merchant_raw or "",
                txn.category.name if txn.category else "",
                txn.account.display_name if txn.account and txn.account.display_name else (
                    txn.account.issuer_name if txn.account else ""
                ),
                txn.needs_review,
                txn.confidence_score,
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )
