import base64
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# googleapiclient uses httplib2, which verifies TLS against certifi's public-CA bundle rather
# than the OS trust store. On networks behind a TLS-inspecting proxy (e.g. corporate Zscaler),
# certifi doesn't have the proxy's root CA, so requests fail with CERTIFICATE_VERIFY_FAILED even
# though the OS trust store (and thus stdlib ssl with default args) already trusts it. Point
# httplib2 at the OS bundle, which is kept in sync with proxy-injected roots, instead. This MUST
# run before `httplib2` is imported (directly or via googleapiclient below) — httplib2.CA_CERTS
# is a module-level constant evaluated once at import time, so setting the env var afterwards
# has no effect.
os.environ.setdefault("HTTPLIB2_CA_CERTS", "/etc/ssl/certs/ca-bundle.pem")

from google.oauth2.credentials import Credentials  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402


@dataclass
class GmailMessage:
    gmail_message_id: str
    history_id: str | None
    sender: str | None
    subject: str | None
    snippet: str | None
    body_text: str | None
    received_at: datetime | None


def _build_service(access_token: str):
    credentials = Credentials(token=access_token)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _exclusion_query(blacklisted_senders: list[str] | None) -> str:
    """Builds Gmail search '-from:' exclusion terms so blacklisted senders are never fetched
    at all — cheaper and cleaner than filtering after fetch, at the cost of losing visibility
    into excluded mail entirely (nothing is stored, so a wrongly-blacklisted sender's real
    transactions vanish with no trace to notice the gap)."""
    if not blacklisted_senders:
        return ""
    return " ".join(f"-from:{sender}" for sender in blacklisted_senders)


def list_recent_message_ids(
    access_token: str, max_results: int, blacklisted_senders: list[str] | None = None
) -> list[str]:
    service = _build_service(access_token)
    query = _exclusion_query(blacklisted_senders)
    response = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query or None, labelIds=["INBOX"])
        .execute()
    )
    return [m["id"] for m in response.get("messages", [])]


def list_message_ids_in_range(
    access_token: str, date_from: date, date_to: date, blacklisted_senders: list[str] | None = None
) -> list[str]:
    """Fetches every inbox message received within [date_from, date_to] (both inclusive),
    paginating through all results — unlike list_recent_message_ids, this has no result cap.

    Gmail's after:/before: search operators are date-only (no time-of-day) and before: is
    exclusive, so date_to is advanced by one day to make the requested end date inclusive.
    """
    service = _build_service(access_token)
    date_query = f"after:{date_from.strftime('%Y/%m/%d')} before:{(date_to + timedelta(days=1)).strftime('%Y/%m/%d')}"
    exclusion = _exclusion_query(blacklisted_senders)
    query = f"{date_query} {exclusion}".strip()

    message_ids: list[str] = []
    page_token: str | None = None
    while True:
        request = service.users().messages().list(
            userId="me", q=query, labelIds=["INBOX"], pageToken=page_token
        )
        response = request.execute()
        message_ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def _extract_header(headers: list[dict], name: str) -> str | None:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")
    return None


def _walk_parts_for_text(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data.encode()).decode(errors="replace")

    text_parts: list[str] = []
    for part in payload.get("parts", []) or []:
        text_parts.append(_walk_parts_for_text(part))

    if text_parts:
        return "\n".join(t for t in text_parts if t)

    if mime_type == "text/html" and body_data:
        return base64.urlsafe_b64decode(body_data.encode()).decode(errors="replace")

    return ""


def get_message(access_token: str, message_id: str) -> GmailMessage:
    service = _build_service(access_token)
    raw = service.users().messages().get(userId="me", id=message_id, format="full").execute()

    headers = raw.get("payload", {}).get("headers", [])
    sender = _extract_header(headers, "From")
    subject = _extract_header(headers, "Subject")
    snippet = raw.get("snippet")
    body_text = _walk_parts_for_text(raw.get("payload", {}))

    internal_date_ms = raw.get("internalDate")
    received_at = (
        datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc) if internal_date_ms else None
    )

    return GmailMessage(
        gmail_message_id=raw["id"],
        history_id=raw.get("historyId"),
        sender=sender,
        subject=subject,
        snippet=snippet,
        body_text=body_text,
        received_at=received_at,
    )
