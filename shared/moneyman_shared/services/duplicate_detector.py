import difflib
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.transaction import Transaction

# Fuzzy duplicate detection: catches the same real-world transaction notified twice (e.g. a
# "pending" then "posted" alert for one charge, or two separate notifications for one event)
# without relying on any extracted reference/UTR number — those come from free-form email text
# the LLM can misread (see: the account_last4 hallucination bug), so trusting an "ID" for dedup
# risks merging unrelated transactions that happen to share a bad guess. Instead this matches on
# fields that are either exact/structural (account, currency, type, calendar day) or numeric
# (amount) — deliberately conservative: same account only, since a debit on account A and a
# credit on account B for the same amount/day are two legitimate legs of one transfer, not a
# duplicate of each other.

def _merchant_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def find_duplicate_candidate(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID | None,
    currency: str,
    amount: float,
    txn_type: str,
    txn_date: date | None,
    merchant_normalized: str | None,
    exclude_transaction_id: uuid.UUID | None = None,
) -> Transaction | None:
    """Looks for an existing transaction that's likely the same real-world event as the one
    about to be created. Requires an account (no account_id means nothing to match against —
    a transaction with no resolved account can't be compared to another this way) and a
    txn_date (undated transactions aren't compared, since "same calendar day" can't be checked)."""
    if account_id is None or txn_date is None:
        return None

    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.account_id == account_id,
        Transaction.currency == currency,
        Transaction.amount == amount,
        Transaction.txn_type == txn_type,
        Transaction.txn_date == txn_date,
    )
    if exclude_transaction_id is not None:
        stmt = stmt.where(Transaction.id != exclude_transaction_id)

    result = await db.execute(stmt)
    candidates = result.scalars().all()
    if not candidates:
        return None

    # Multiple same-account/amount/type/day matches (e.g. two genuine same-amount purchases):
    # prefer the one with the most similar merchant text, but still return the best candidate
    # even without merchant text — amount+account+day match is already a meaningful signal.
    return max(candidates, key=lambda c: _merchant_similarity(merchant_normalized, c.merchant_normalized))
