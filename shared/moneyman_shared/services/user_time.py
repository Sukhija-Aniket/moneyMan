from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def today_for_user(user_timezone: str) -> date:
    """The current calendar date as seen by a user in their configured IANA timezone.

    Falls back to UTC if the stored value isn't a valid zoneinfo key (shouldn't happen —
    validated on write in PATCH /auth/me — but a bad row shouldn't 500 every date check).
    """
    try:
        tz = ZoneInfo(user_timezone)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date()
