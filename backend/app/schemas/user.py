import uuid

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    picture_url: str | None = None
    llm_provider: str
    timezone: str


class UserSettingsUpdate(BaseModel):
    llm_provider: str | None = None
    timezone: str | None = None
