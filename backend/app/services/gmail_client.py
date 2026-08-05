import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# googleapiclient uses httplib2, which verifies TLS against certifi's public-CA bundle rather
# than the OS trust store. On networks behind a TLS-inspecting proxy (e.g. corporate Zscaler),
# certifi doesn't have the proxy's root CA, so requests fail with CERTIFICATE_VERIFY_FAILED even
# though the OS trust store (and thus stdlib ssl with default args) already trusts it. Point
# httplib2 at the OS bundle, which is kept in sync with proxy-injected roots, instead.
os.environ.setdefault("HTTPLIB2_CA_CERTS", "/etc/ssl/certs/ca-bundle.pem")


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


def list_recent_message_ids(access_token: str, max_results: int) -> list[str]:
    service = _build_service(access_token)
    response = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, labelIds=["INBOX"])
        .execute()
    )
    return [m["id"] for m in response.get("messages", [])]


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
