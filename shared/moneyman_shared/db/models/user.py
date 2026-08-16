import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

if TYPE_CHECKING:
    from moneyman_shared.db.models.account import Account
    from moneyman_shared.db.models.blacklisted_sender import BlacklistedSender
    from moneyman_shared.db.models.category import Category
    from moneyman_shared.db.models.gmail_watch_state import GmailWatchState
    from moneyman_shared.db.models.oauth_token import OAuthToken
    from moneyman_shared.db.models.raw_email import RawEmail
    from moneyman_shared.db.models.transaction import Transaction


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    picture_url: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_provider: Mapped[str] = mapped_column(String, nullable=False, server_default="anthropic")
    timezone: Mapped[str] = mapped_column(String, nullable=False, server_default="UTC")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    oauth_token: Mapped["OAuthToken | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    gmail_watch_state: Mapped["GmailWatchState | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    raw_emails: Mapped[list["RawEmail"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    categories: Mapped[list["Category"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    accounts: Mapped[list["Account"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    blacklisted_senders: Mapped[list["BlacklistedSender"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
