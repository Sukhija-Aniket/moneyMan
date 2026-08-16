import uuid
from datetime import datetime

from pydantic import BaseModel


class BlacklistedSenderCreate(BaseModel):
    sender: str


class BlacklistedSenderOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    sender: str
    created_at: datetime
