import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.config import get_settings
from moneyman_shared.db.models.account import Account
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
from moneyman_shared.services.gate1_filter import passes_gate1

# The actual Gmail-fetch + classify/extract + DB-write pipeline, shared by the backend's
# plain "Sync now" path (POST /gmail/sync with no range) and the worker (which runs this
# for every published gmail-sync-jobs range-sync job).


class GmailSyncError(Exception):
    """Raised for failures that should abort the whole sync (no Gmail connection, token
    refresh failure, message listing failure) — as opposed to a single email's processing
    failing, which is caught and counted per-email instead."""


@dataclass
class GmailSyncCounters:
    fetched: int = 0
    gate1_rejected: int = 0
    classify_failed: int = 0
    classified_non_transaction: int = 0
    extracted_accepted: int = 0
    extracted_needs_review: int = 0
    extracted_discarded: int = 0
    extract_failed: int = 0

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "gate1_rejected": self.gate1_rejected,
            "classify_failed": self.classify_failed,
            "classified_non_transaction": self.classified_non_transaction,
            "extracted_accepted": self.extracted_accepted,
            "extracted_needs_review": self.extracted_needs_review,
            "extracted_discarded": self.extracted_discarded,
            "extract_failed": self.extract_failed,
        }


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
    last4 = _sanitize_last4(last4)
    if not issuer_name and not last4:
        return None

    stmt = select(Account).where(
        Account.user_id == user_id,
        Account.issuer_name == issuer_name,
        Account.last4 == last4,
        Account.account_type == account_type,
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


async def run_gmail_sync(
    db: AsyncSession,
    user: User,
    date_from: date | None = None,
    date_to: date | None = None,
) -> GmailSyncCounters:
    """Runs one full sync pass for `user`: fetches Gmail messages (either the most recent
    GMAIL_SYNC_MAX_RESULTS, or every message in [date_from, date_to] if both are given),
    classifies/extracts each new one, and writes raw_emails/accounts/transactions rows.

    Raises GmailSyncError for failures that abort the whole run. Per-email failures
    (classify/extract errors, malformed messages) are caught and counted, not raised.
    """
    settings = get_settings()
    oauth_token = await _get_oauth_token(db, user.id)

    now = datetime.now(timezone.utc)
    if oauth_token.token_expiry is not None and oauth_token.token_expiry <= now:
        if not oauth_token.refresh_token_enc:
            raise GmailSyncError(
                "Gmail access token expired and no refresh token is available. Sign in with Google again."
            )
        refresh_token = token_crypto.decrypt(oauth_token.refresh_token_enc)
        try:
            refreshed = google_oauth.refresh_access_token(refresh_token)
        except Exception as exc:
            raise GmailSyncError(
                f"Failed to refresh Gmail access token: {exc}. Sign in with Google again."
            ) from exc

        oauth_token.access_token_enc = token_crypto.encrypt(refreshed.access_token)
        oauth_token.token_expiry = refreshed.token_expiry
        await db.commit()

    access_token = token_crypto.decrypt(oauth_token.access_token_enc)

    counters = GmailSyncCounters()
    blacklisted_senders = await get_blacklisted_senders(db, user.id)

    try:
        if date_from is not None and date_to is not None:
            message_ids = gmail_client.list_message_ids_in_range(
                access_token, date_from, date_to, blacklisted_senders
            )
        else:
            message_ids = gmail_client.list_recent_message_ids(
                access_token, settings.GMAIL_SYNC_MAX_RESULTS, blacklisted_senders
            )
    except Exception as exc:
        raise GmailSyncError(f"Failed to list Gmail messages: {exc}") from exc

    counters.fetched = len(message_ids)

    for gmail_message_id in message_ids:
        existing = await db.execute(
            select(RawEmail).where(
                RawEmail.user_id == user.id,
                RawEmail.gmail_message_id == gmail_message_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        try:
            message = gmail_client.get_message(access_token, gmail_message_id)
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
            counters.gate1_rejected += 1
            await db.commit()
            continue

        try:
            stage_a = classification_service.classify_email(
                message.subject, message.sender, message.snippet, provider=user.llm_provider
            )
        except Exception:
            raw_email.classification = "classify_failed"
            counters.classify_failed += 1
            await db.commit()
            continue

        if not stage_a.is_transaction_email:
            raw_email.classification = "not_transaction"
            counters.classified_non_transaction += 1
            await db.commit()
            continue

        raw_email.classification = "candidate"
        await db.commit()

        try:
            extraction = extraction_service.extract_transaction(
                message.subject, message.sender, message.body_text, provider=user.llm_provider
            )
        except Exception:
            raw_email.classification = "extract_failed"
            counters.extract_failed += 1
            await db.commit()
            continue

        # Confidence handling per plan §4.2.
        if not extraction.is_transaction or extraction.confidence < 0.5:
            raw_email.classification = "not_transaction"
            counters.extracted_discarded += 1
            await db.commit()
            continue

        # Amount/currency/date/last4 come from a templated, structured part of the email —
        # a regex pass extracts them deterministically and more reliably than the LLM (which
        # can hallucinate, e.g. picking up an unrelated digit sequence from an email footer
        # as the year). Prefer the deterministic result for these fields; fall back to the
        # LLM's values only when the regex pass finds nothing.
        deterministic = extract_deterministic(message.subject, message.body_text, message.received_at)

        amount = deterministic.amount if deterministic.amount is not None else extraction.amount
        currency = deterministic.currency or extraction.currency
        account_last4 = deterministic.account_last4 or extraction.account_last4

        needs_review = extraction.confidence < 0.85 or amount is None
        # The LLM can fabricate a plausible-looking last4 from an unrelated digit sequence
        # (order/reference IDs, etc.) — the regex extractor only matches an actual "ending in"/
        # masked-digits pattern, so when it finds nothing but the LLM claims a value anyway,
        # that value is unverified. Still use it (some real account numbers appear in formats
        # the regex doesn't cover), but flag for review instead of trusting it silently.
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

        # Boilerplate footers ("Credit/Debit Card number", "RuPay Credit Card") make debit/
        # credit direction another field the LLM can get backwards even with clear language
        # in the email ("has been credited with...") — the deterministic pass only counts an
        # explicit direction keyword found right next to the amount itself. When it disagrees
        # with the LLM (rather than one of them simply finding nothing), flag for review —
        # that mismatch means at least one of the two is wrong, so neither should be trusted
        # silently.
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

        # needs_review here just means "extraction was uncertain enough that a human should
        # look" — it always starts a transaction as review_status="pending" (untouched by a
        # human yet). The other statuses (confirmed/not_transaction/duplicate) are set later,
        # only by an explicit human action in the Review Queue — sync never assigns them.
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
            ambiguity_notes=ambiguity_notes,
            extraction_raw_json=extraction.raw,
        )
        db.add(transaction)
        raw_email.classification = "extracted"

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue

        if needs_review:
            counters.extracted_needs_review += 1
        else:
            counters.extracted_accepted += 1

    return counters
