import os
from dataclasses import dataclass
from datetime import datetime, timezone

import google.auth.transport.requests
import google.oauth2.credentials
import google.oauth2.id_token
from google_auth_oauthlib.flow import Flow

from moneyman_shared.config import get_settings

# Google may grant a narrower scope set than requested (e.g. a restricted scope like
# gmail.readonly gets silently dropped if consent-screen propagation hasn't caught up yet).
# oauthlib treats any requested-vs-granted scope mismatch as a hard error by default;
# relax that so we can inspect the actually-granted scope instead of crashing.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


@dataclass
class GoogleUserInfo:
    google_sub: str
    email: str
    full_name: str | None
    picture_url: str | None


@dataclass
class GoogleTokenResult:
    access_token: str
    refresh_token: str | None
    scope: str
    token_expiry: datetime | None
    user_info: GoogleUserInfo


def _client_config() -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }


def build_flow(code_verifier: str | None = None) -> Flow:
    settings = get_settings()
    flow = Flow.from_client_config(
        _client_config(), scopes=GMAIL_SCOPES, code_verifier=code_verifier
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def get_authorization_url(state: str) -> tuple[str, str]:
    flow = build_flow()
    # access_type=offline + prompt=consent guarantees a refresh_token is issued,
    # including on repeat logins (Google only returns it on the first consent otherwise).
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url, flow.code_verifier


def exchange_code_for_tokens(code: str, code_verifier: str) -> GoogleTokenResult:
    flow = build_flow(code_verifier=code_verifier)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    request = google.auth.transport.requests.Request()
    id_info = google.oauth2.id_token.verify_oauth2_token(
        credentials.id_token, request, audience=get_settings().GOOGLE_CLIENT_ID
    )

    user_info = GoogleUserInfo(
        google_sub=id_info["sub"],
        email=id_info["email"],
        full_name=id_info.get("name"),
        picture_url=id_info.get("picture"),
    )

    expiry = credentials.expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    return GoogleTokenResult(
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        scope=" ".join(credentials.scopes or GMAIL_SCOPES),
        token_expiry=expiry,
        user_info=user_info,
    )


def refresh_access_token(refresh_token: str) -> GoogleTokenResult | None:
    settings = get_settings()
    credentials = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    expiry = credentials.expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    return GoogleTokenResult(
        access_token=credentials.token,
        refresh_token=credentials.refresh_token or refresh_token,
        scope=" ".join(credentials.scopes or GMAIL_SCOPES),
        token_expiry=expiry,
        user_info=GoogleUserInfo(google_sub="", email="", full_name=None, picture_url=None),
    )
