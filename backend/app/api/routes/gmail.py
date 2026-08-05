import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.account import Account
from app.db.models.oauth_token import OAuthToken
from app.db.models.raw_email import RawEmail
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.gmail import GmailStatus, GmailSyncResult
from app.services import classification_service, extraction_service, gmail_client, google_oauth, token_crypto
from app.services.gate1_filter import passes_gate1

router = APIRouter(prefix="/gmail", tags=["gmail"])
settings = get_settings()


async def _get_oauth_token(db: AsyncSession, user_id: uuid.UUID) -> OAuthToken:
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Gmail account connected. Sign in with Google first.",
        )
    return token


async def _get_or_create_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    issuer_name: str | None,
    last4: str | None,
    account_type: str | None,
) -> Account | None:
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


@router.post("/sync", response_model=GmailSyncResult)
async def sync_now(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GmailSyncResult:
    oauth_token = await _get_oauth_token(db, current_user.id)

    now = datetime.now(timezone.utc)
    if oauth_token.token_expiry is not None and oauth_token.token_expiry <= now:
        if not oauth_token.refresh_token_enc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gmail access token expired and no refresh token is available. Sign in with Google again.",
            )
        refresh_token = token_crypto.decrypt(oauth_token.refresh_token_enc)
        try:
            refreshed = google_oauth.refresh_access_token(refresh_token)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to refresh Gmail access token: {exc}. Sign in with Google again.",
            ) from exc

        oauth_token.access_token_enc = token_crypto.encrypt(refreshed.access_token)
        oauth_token.token_expiry = refreshed.token_expiry
        await db.commit()

    access_token = token_crypto.decrypt(oauth_token.access_token_enc)

    counters = {
        "fetched": 0,
        "gate1_rejected": 0,
        "classified_non_transaction": 0,
        "extracted_accepted": 0,
        "extracted_needs_review": 0,
        "extracted_discarded": 0,
        "extract_failed": 0,
    }

    try:
        message_ids = gmail_client.list_recent_message_ids(access_token, settings.GMAIL_SYNC_MAX_RESULTS)
    except Exception as exc:  # Gmail API / auth failures surface as a clear 502
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to list Gmail messages: {exc}"
        ) from exc

    counters["fetched"] = len(message_ids)

    for gmail_message_id in message_ids:
        existing = await db.execute(
            select(RawEmail).where(
                RawEmail.user_id == current_user.id,
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
            user_id=current_user.id,
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
            counters["gate1_rejected"] += 1
            await db.commit()
            continue

        stage_a = classification_service.classify_email(message.subject, message.sender, message.snippet)
        if not stage_a.is_transaction_email:
            raw_email.classification = "not_transaction"
            counters["classified_non_transaction"] += 1
            await db.commit()
            continue

        raw_email.classification = "candidate"
        await db.commit()

        try:
            extraction = extraction_service.extract_transaction(
                message.subject, message.sender, message.body_text
            )
        except Exception:
            raw_email.classification = "extract_failed"
            counters["extract_failed"] += 1
            await db.commit()
            continue

        # Confidence handling per plan §4.2.
        if not extraction.is_transaction or extraction.confidence < 0.5:
            raw_email.classification = "not_transaction"
            counters["extracted_discarded"] += 1
            await db.commit()
            continue

        needs_review = extraction.confidence < 0.85 or extraction.amount is None

        txn_date = None
        if extraction.txn_date:
            try:
                txn_date = datetime.strptime(extraction.txn_date, "%Y-%m-%d").date()
            except ValueError:
                needs_review = True

        account = await _get_or_create_account(
            db,
            current_user.id,
            extraction.issuer_or_bank_name,
            extraction.account_last4,
            extraction.account_type,
        )

        transaction = Transaction(
            user_id=current_user.id,
            raw_email_id=raw_email.id,
            account_id=account.id if account else None,
            amount=extraction.amount or 0,
            currency=extraction.currency or "USD",
            txn_type=extraction.txn_type or "debit",
            merchant_raw=extraction.merchant_or_counterparty,
            merchant_normalized=extraction.merchant_or_counterparty,
            txn_date=txn_date,
            confidence_score=extraction.confidence,
            needs_review=needs_review,
            ambiguity_notes=extraction.ambiguity_notes,
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
            counters["extracted_needs_review"] += 1
        else:
            counters["extracted_accepted"] += 1

    return GmailSyncResult(**counters)


@router.get("/status", response_model=GmailStatus)
async def gmail_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GmailStatus:
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == current_user.id))
    token = result.scalar_one_or_none()
    if token is None:
        return GmailStatus(connected=False)

    return GmailStatus(
        connected=True,
        scope=token.scope,
        token_expiry=token.token_expiry.isoformat() if token.token_expiry else None,
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
