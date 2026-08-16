import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.blacklisted_sender import BlacklistedSender


async def get_blacklisted_senders(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(select(BlacklistedSender.sender).where(BlacklistedSender.user_id == user_id))
    return [row[0] for row in result.all()]
