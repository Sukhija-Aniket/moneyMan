import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.blacklisted_sender import BlacklistedSender
from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import get_db
from app.deps import get_current_user
from app.schemas.blacklist import BlacklistedSenderCreate, BlacklistedSenderOut

router = APIRouter(prefix="/gmail/blacklist", tags=["gmail"])


@router.get("", response_model=list[BlacklistedSenderOut])
async def list_blacklisted_senders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BlacklistedSenderOut]:
    result = await db.execute(
        select(BlacklistedSender)
        .where(BlacklistedSender.user_id == current_user.id)
        .order_by(BlacklistedSender.sender)
    )
    return [BlacklistedSenderOut.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=BlacklistedSenderOut, status_code=status.HTTP_201_CREATED)
async def add_blacklisted_sender(
    payload: BlacklistedSenderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BlacklistedSenderOut:
    sender = payload.sender.strip()
    if not sender:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sender cannot be empty.")

    entry = BlacklistedSender(user_id=current_user.id, sender=sender)
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sender already blacklisted.") from exc
    await db.refresh(entry)
    return BlacklistedSenderOut.model_validate(entry)


@router.delete("/{sender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_blacklisted_sender(
    sender_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(BlacklistedSender).where(
            BlacklistedSender.id == sender_id, BlacklistedSender.user_id == current_user.id
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blacklist entry not found.")
    await db.delete(entry)
    await db.commit()
