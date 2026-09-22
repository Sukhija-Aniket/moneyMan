import asyncio
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.config import get_settings
from moneyman_shared.db.models.account import Account
from moneyman_shared.db.models.fetched_range import FetchedRange
from moneyman_shared.db.models.oauth_token import OAuthToken
from moneyman_shared.db.models.raw_email import RawEmail
from moneyman_shared.db.models.review_status import ReviewStatus
from moneyman_shared.db.models.transaction import Transaction
from moneyman_shared.db.models.user import User
from moneyman_shared.services import (
    classification_service,
    extraction_service,
    gmail_client,
    google_oauth,
    token_crypto,
)
from moneyman_shared.services.blacklist_service import get_blacklisted_senders
from moneyman_shared.services.deterministic_extractor import extract_deterministic
from moneyman_shared.services.duplicate_detector import find_duplicate_candidate
from moneyman_shared.services.coverage import compute_gaps, get_covered_ranges
from moneyman_shared.services.gate1_filter import passes_gate1

# The Gmail-fetch + classify/extract + DB-write pipeline used by the worker's two-stage
# range-sync (fetch_and_queue_candidates + extract_one_email, one per published
# gmail-sync-jobs/email-extraction-jobs message).


class GmailSyncError(Exception):
    """Raised for failures that should abort the whole sync (no Gmail connection, token
    refresh failure, message listing failure) — as opposed to a single email's processing
    failing, which is caught and counted per-email instead."""


async def _get_oauth_token(db: AsyncSession, user_id: uuid.UUID) -> OAuthToken:
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if token is None:
        raise GmailSyncError("No Gmail account connected. Sign in with Google first.")
    return token


def _sanitize_last4(last4: str | None) -> str | None:
    """The LLM is instructed to return exactly 4 digits, but local/smaller models don't always
    comply (e.g. 'XX1516' with a masking prefix) — defensively extract the last 4 digits
    ourselves rather than let a malformed value crash the accounts.last4 (varchar(4)) insert."""
    if not last4:
        return None
    digits = "".join(ch for ch in last4 if ch.isdigit())
    return digits[-4:] if len(digits) >= 4 else None


async def _get_or_create_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    issuer_name: str | None,
    last4: str | None,
    account_type: str | None,
) -> Account | None:
    """Groups by last4 alone — issuer_name/account_type are both LLM-extracted and
    inconsistent across emails for the same real account (e.g. "Axis Bank" vs "Axis Bank
    Ltd.", debit_card vs credit_card for the same card), so an exact match on them
    fragmented one real account into several `accounts` rows. last4 is deterministic (regex-
    extracted, see extract_deterministic), so it's the reliable grouping key. Falls back to
    grouping by issuer_name alone only when an email has no last4 at all (e.g. a payment
    notification with no card/account number mentioned)."""
    last4 = _sanitize_last4(last4)
    if not issuer_name and not last4:
        return None

    if last4:
        stmt = select(Account).where(Account.user_id == user_id, Account.last4 == last4)
    else:
        stmt = select(Account).where(
            Account.user_id == user_id, Account.last4.is_(None), Account.issuer_name == issuer_name
        )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is not None:
        return account

    account = Account(
        user_id=user_id,
        issuer_name=issuer_name,
        last4=last4,
        account_type=account_type,
    )
    db.add(account)
    await db.flush()
    return account


@dataclass
class FetchResult:
    fetched: int
    gate1_rejected: int
    candidate_raw_email_ids: list[uuid.UUID]


async def _get_valid_access_token(db: AsyncSession, user: User) -> str:
    """Used by the fetch stage (range syncs) — looks up the user's OAuth token and
    refreshes it if expired."""
    oauth_token = await _get_oauth_token(db, user.id)

    now = datetime.now(timezone.utc)
    if oauth_token.token_expiry is not None and oauth_token.token_expiry <= now:
        if not oauth_token.refresh_token_enc:
            raise GmailSyncError(
                "Gmail access token expired and no refresh token is available. Sign in with Google again."
            )
        refresh_token = token_crypto.decrypt(oauth_token.refresh_token_enc)
        try:
            refreshed = await asyncio.to_thread(google_oauth.refresh_access_token, refresh_token)
        except Exception as exc:
            raise GmailSyncError(
                f"Failed to refresh Gmail access token: {exc}. Sign in with Google again."
            ) from exc

        oauth_token.access_token_enc = token_crypto.encrypt(refreshed.access_token)
        oauth_token.token_expiry = refreshed.token_expiry
        await db.commit()

    return token_crypto.decrypt(oauth_token.access_token_enc)


_TERMINAL_VERDICTS = ("not_transaction", "extracted")
_RETRIABLE_TERMINAL = ("pending", "candidate", "classify_failed", "extract_failed")


async def _candidates_from_existing_raw_emails(db: AsyncSession, user: User, date_from: date, date_to: date) -> FetchResult:
    """Skips Gmail entirely: derives candidates for an already-fetched date range straight
    from raw_emails. Used when fetched_ranges shows this range was already listed/fetched on
    a prior attempt — re-fetching from Gmail would be pure waste, since nothing about the
    fetched data itself needs to change, only (possibly) reclassification of rows that
    previously failed."""
    result = await db.execute(
        select(RawEmail).where(
            RawEmail.user_id == user.id,
            RawEmail.received_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc),
            RawEmail.received_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
        )
    )
    rows = result.scalars().all()
    candidate_ids = [row.id for row in rows if row.classification in _RETRIABLE_TERMINAL]
    gate1_rejected = sum(1 for row in rows if row.classification == "not_transaction")
    return FetchResult(fetched=len(rows), gate1_rejected=gate1_rejected, candidate_raw_email_ids=candidate_ids)


async def fetch_and_queue_candidates(
    db: AsyncSession,
    user: User,
    date_from: date | None,
    date_to: date | None,
    skip_gmail_if_already_fetched: bool = False,
) -> FetchResult:
    """Fetch-stage logic for the two-stage range-sync pipeline (see docs/design.md): lists
    Gmail messages in [date_from, date_to], runs Gate 1, and writes raw_emails rows — but
    does NOT classify/extract. Returns the ids of raw_emails rows that passed Gate 1 (i.e.
    became a "candidate"), for the caller (the worker's fetch-stage consumer) to publish one
    EmailExtractionJob per id. Raises GmailSyncError for whole-range failures (no Gmail
    connection, token refresh failure, message listing failure).

    If `skip_gmail_if_already_fetched` and [date_from, date_to] is fully covered by
    fetched_ranges (this exact range was already listed/fetched from Gmail on a prior
    attempt — see moneyman_shared.db.models.fetched_range), skips the Gmail API calls
    entirely and derives candidates directly from existing raw_emails rows instead. This is
    what lets a classify_failed/extract_failed retry never re-pay Gmail's list/get_message
    cost."""
    settings = get_settings()

    if skip_gmail_if_already_fetched and date_from is not None and date_to is not None:
        covered = await get_covered_ranges(db, FetchedRange, user.id)
        if not compute_gaps(covered, date_from, date_to):
            return await _candidates_from_existing_raw_emails(db, user, date_from, date_to)

    access_token = await _get_valid_access_token(db, user)
    blacklisted_senders = await get_blacklisted_senders(db, user.id)

    try:
        if date_from is not None and date_to is not None:
            message_ids = await asyncio.to_thread(
                gmail_client.list_message_ids_in_range, access_token, date_from, date_to, blacklisted_senders
            )
        else:
            message_ids = await asyncio.to_thread(
                gmail_client.list_recent_message_ids,
                access_token,
                settings.GMAIL_SYNC_MAX_RESULTS,
                blacklisted_senders,
            )
    except Exception as exc:
        raise GmailSyncError(f"Failed to list Gmail messages: {exc}") from exc

    gate1_rejected = 0
    candidate_ids: list[uuid.UUID] = []

    for gmail_message_id in message_ids:
        existing = await db.execute(
            select(RawEmail).where(
                RawEmail.user_id == user.id,
                RawEmail.gmail_message_id == gmail_message_id,
            )
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row is not None:
            # Already fetched (e.g. this segment was redelivered) — re-queue it as a
            # candidate unless it already reached a genuine verdict ("not_transaction" or
            # "extracted"). "classify_failed"/"extract_failed" are transient failures (an LLM
            # call error), not verdicts — always eligible for reclassification on a later
            # sync touching this email again, not just a one-off manual fix.
            if existing_row.classification in _RETRIABLE_TERMINAL:
                candidate_ids.append(existing_row.id)
            continue

        try:
            message = await asyncio.to_thread(gmail_client.get_message, access_token, gmail_message_id)
        except Exception:
            continue

        raw_email = RawEmail(
            user_id=user.id,
            gmail_message_id=message.gmail_message_id,
            history_id=message.history_id,
            sender=message.sender,
            subject=message.subject,
            snippet=message.snippet,
            body_text=message.body_text,
            received_at=message.received_at,
            classification="pending",
        )
        db.add(raw_email)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            continue

        if not passes_gate1(message.subject, message.snippet):
            raw_email.classification = "not_transaction"
            gate1_rejected += 1
            await db.commit()
            continue

        raw_email.classification = "candidate"
        await db.commit()
        candidate_ids.append(raw_email.id)

    return FetchResult(
        fetched=len(message_ids), gate1_rejected=gate1_rejected, candidate_raw_email_ids=candidate_ids
    )


async def extract_one_email(db: AsyncSession, user: User, raw_email_id: uuid.UUID) -> str:
    """Extraction-stage logic for the two-stage range-sync pipeline (see docs/design.md):
    classifies + extracts a single already-fetched raw_emails row and writes its Transaction
    if applicable. Returns one of "extracted" | "not_transaction" | "classify_failed" |
    "extract_failed" — the EmailExtractionEvent outcome. Idempotent for genuine verdicts:
    re-running for a raw_email_id already "not_transaction" or "extracted" is a safe no-op
    (echoes the stored outcome), so redelivery of the same EmailExtractionJob never
    double-writes a Transaction. "classify_failed"/"extract_failed" are transient failures
    (an LLM call error), not verdicts — always retried rather than echoed, whether this call
    is a genuine job redelivery or a fresh EmailExtractionJob from a later sync re-queueing
    this email."""
    result = await db.execute(select(RawEmail).where(RawEmail.id == raw_email_id))
    raw_email = result.scalar_one_or_none()
    if raw_email is None:
        return "extract_failed"

    if raw_email.classification in _TERMINAL_VERDICTS:
        return raw_email.classification

    try:
        stage_a = await asyncio.to_thread(
            classification_service.classify_email,
            raw_email.subject,
            raw_email.sender,
            raw_email.snippet,
            provider=user.llm_provider,
        )
    except Exception:
        raw_email.classification = "classify_failed"
        await db.commit()
        return "classify_failed"

    if not stage_a.is_transaction_email:
        raw_email.classification = "not_transaction"
        await db.commit()
        return "not_transaction"

    raw_email.classification = "candidate"
    await db.commit()

    try:
        extraction = await asyncio.to_thread(
            extraction_service.extract_transaction,
            raw_email.subject,
            raw_email.sender,
            raw_email.body_text,
            provider=user.llm_provider,
        )
    except Exception:
        raw_email.classification = "extract_failed"
        await db.commit()
        return "extract_failed"

    # Confidence handling per plan §4.2.
    if not extraction.is_transaction or extraction.confidence < 0.5:
        raw_email.classification = "not_transaction"
        await db.commit()
        return "not_transaction"

    # Demat/brokerage securities activity (buy/sell orders, etc.) is real money movement but
    # not a bank/card transaction, so debit/credit doesn't cleanly apply -- exclude it the same
    # way as not_transaction, but only when confident. A low-confidence call here falls through
    # to the normal needs_review path below instead of being silently dropped, so an email that
    # might actually be a real bank/card transaction still reaches a human.
    if extraction.is_bank_or_card_txn is False and extraction.confidence >= 0.85:
        raw_email.classification = "not_transaction"
        await db.commit()
        return "not_transaction"

    deterministic = extract_deterministic(raw_email.subject, raw_email.body_text, raw_email.received_at)

    amount = deterministic.amount if deterministic.amount is not None else extraction.amount
    currency = deterministic.currency or extraction.currency
    account_last4 = deterministic.account_last4 or extraction.account_last4

    needs_review = extraction.confidence < 0.85 or amount is None
    if extraction.is_bank_or_card_txn is False:
        needs_review = True
    if deterministic.account_last4 is None and extraction.account_last4 is not None:
        needs_review = True

    txn_date = deterministic.txn_date
    if txn_date is None and extraction.txn_date:
        try:
            txn_date = datetime.strptime(extraction.txn_date, "%Y-%m-%d").date()
        except ValueError:
            needs_review = True

    try:
        account = await _get_or_create_account(
            db,
            user.id,
            extraction.issuer_or_bank_name,
            account_last4,
            extraction.account_type,
        )
    except Exception:
        await db.rollback()
        account = None
        needs_review = True

    txn_type = deterministic.txn_type or extraction.txn_type or "debit"
    if (
        deterministic.txn_type is not None
        and extraction.txn_type is not None
        and deterministic.txn_type != extraction.txn_type
    ):
        needs_review = True
    final_currency = currency or "USD"
    final_amount = amount or 0
    merchant = extraction.merchant_or_counterparty

    duplicate_of = await find_duplicate_candidate(
        db,
        user.id,
        account.id if account else None,
        final_currency,
        final_amount,
        txn_type,
        txn_date,
        merchant,
    )
    ambiguity_notes = extraction.ambiguity_notes
    if duplicate_of is not None:
        needs_review = True
        note = f"Possible duplicate of transaction {duplicate_of.id} (same account/amount/type/day)."
        ambiguity_notes = f"{ambiguity_notes} {note}".strip() if ambiguity_notes else note

    review_status: ReviewStatus = "pending" if needs_review else "confirmed"

    transaction = Transaction(
        user_id=user.id,
        raw_email_id=raw_email.id,
        account_id=account.id if account else None,
        duplicate_of_transaction_id=duplicate_of.id if duplicate_of else None,
        amount=final_amount,
        currency=final_currency,
        txn_type=txn_type,
        merchant_raw=merchant,
        merchant_normalized=merchant,
        txn_date=txn_date,
        confidence_score=extraction.confidence,
        review_status=review_status,
        reviewed_by=None if needs_review else "system",
        ambiguity_notes=ambiguity_notes,
        extraction_raw_json=extraction.raw,
    )
    db.add(transaction)
    raw_email.classification = "extracted"

    try:
        await db.commit()
    except SQLAlchemyError:
        # Broader than IntegrityError on purpose: a malformed value from the LLM (e.g. a
        # local Ollama model occasionally emitting the literal string "null" for a numeric
        # field) surfaces here as a DBAPIError/DataError, not a constraint violation — either
        # way, this write can never succeed as-is, so it must land as a terminal
        # "extract_failed" rather than propagate and have the caller nack-and-retry forever.
        await db.rollback()
        raw_email.classification = "extract_failed"
        await db.commit()
        return "extract_failed"

    return "extracted"


def _describe_manual_transaction(
    txn_type: str,
    amount: float,
    currency: str,
    account: Account,
    txn_date: date,
    merchant: str | None,
    note: str | None,
) -> str:
    """Plain-text description stored as the RawEmail body for a user-entered transaction
    (see create_manual_transaction) — a human-readable audit record only, e.g. for "View raw"
    in the UI. Not fed through any extraction — the caller already has the exact structured
    values, so there's nothing to extract and no LLM call is made here."""
    verb = "debited from" if txn_type == "debit" else "credited to" if txn_type == "credit" else "transferred via"
    issuer = account.issuer_name or "your account"
    account_phrase = f"{issuer} (••{account.last4})" if account.last4 else issuer
    merchant_line = f" at {merchant}" if merchant else ""
    note_line = f"\n\nNote: {note}" if note else ""
    return (
        f"{currency} {amount:.2f} was {verb} {account_phrase}{merchant_line} "
        f"on {txn_date.strftime('%d-%m-%Y')}.\n\n"
        f"This transaction was added manually by the user — there is no source email for "
        f"it.{note_line}"
    )


async def create_manual_transaction(
    db: AsyncSession,
    user: User,
    txn_type: str,
    amount: float,
    currency: str,
    account_id: uuid.UUID,
    txn_date: date,
    merchant: str | None,
    note: str | None,
) -> Transaction:
    """User-entered transaction with no backing email (rare — e.g. a cash payment, or a bank
    that never emailed a notification). The caller already provides the exact structured
    values, so there's nothing to extract and no LLM call is made: a RawEmail is still
    created (a plain-text description, purely for "View raw"/audit-trail consistency with
    every other transaction) but the Transaction row is built directly from the given
    fields, confidence_score=1.0, review_status="confirmed" — the user's own input needs no
    review. The account is one the user picks from their existing accounts list (not typed
    freeform), so no fuzzy account matching is needed here — unlike extract_one_email, which
    only ever has LLM-parsed issuer/last4 text to match against."""
    result = await db.execute(select(Account).where(Account.user_id == user.id, Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise ValueError("Account not found")

    body_text = _describe_manual_transaction(txn_type, amount, currency, account, txn_date, merchant, note)
    raw_email = RawEmail(
        user_id=user.id,
        gmail_message_id=f"manual-{uuid.uuid4()}",
        sender="manual-entry@moneyman.local",
        subject=f"Manually added transaction: {currency} {amount:.2f}",
        snippet=body_text[:200],
        body_text=body_text,
        received_at=datetime.now(timezone.utc),
        classification="extracted",
    )
    db.add(raw_email)
    await db.flush()

    transaction = Transaction(
        user_id=user.id,
        raw_email_id=raw_email.id,
        account_id=account.id,
        amount=amount,
        currency=currency,
        txn_type=txn_type,
        merchant_raw=merchant,
        merchant_normalized=merchant,
        txn_date=txn_date,
        confidence_score=1.0,
        review_status="confirmed",
        reviewed_by="human",
        extraction_raw_json={"source": "manual"},
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction

