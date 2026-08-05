import uuid

from pydantic import BaseModel, ConfigDict


class AccountUpdate(BaseModel):
    display_name: str | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issuer_name: str | None = None
    last4: str | None = None
    account_type: str | None = None
    display_name: str | None = None
