# Import shared models first so backend-owned FKs to users.id can always resolve, regardless
# of which module is the first to import anything from app.db.models.
from moneyman_shared.db.models import (
    Account,
    Category,
    FetchedRange,
    GmailWatchState,
    OAuthToken,
    RawEmail,
    SyncedRange,
    Transaction,
    User,
)

from app.db.models.sync_request import SyncRequest
from app.db.models.sync_segment import SyncSegment

__all__ = [
    "Account",
    "Category",
    "FetchedRange",
    "GmailWatchState",
    "OAuthToken",
    "RawEmail",
    "SyncedRange",
    "SyncRequest",
    "SyncSegment",
    "Transaction",
    "User",
]
