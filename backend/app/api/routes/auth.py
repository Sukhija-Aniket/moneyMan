import secrets
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.config import get_settings
from moneyman_shared.db.models.oauth_token import OAuthToken
from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import get_db
from app.deps import create_session_token, get_current_user
from app.schemas.user import UserOut, UserSettingsUpdate
from moneyman_shared.services import google_oauth, token_crypto

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

_OAUTH_STATE_COOKIE = "oauth_state"
_OAUTH_CODE_VERIFIER_COOKIE = "oauth_code_verifier"


@router.get("/google/login")
async def google_login(response: Response) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    auth_url, code_verifier = google_oauth.get_authorization_url(state)

    redirect = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        _OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,
    )
    redirect.set_cookie(
        _OAUTH_CODE_VERIFIER_COOKIE,
        code_verifier,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    expected_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not expected_state or expected_state != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    code_verifier = request.cookies.get(_OAUTH_CODE_VERIFIER_COOKIE)
    if not code_verifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth code verifier")

    token_result = google_oauth.exchange_code_for_tokens(code, code_verifier)

    result = await db.execute(select(User).where(User.google_sub == token_result.user_info.google_sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_sub=token_result.user_info.google_sub,
            email=token_result.user_info.email,
            full_name=token_result.user_info.full_name,
            picture_url=token_result.user_info.picture_url,
        )
        db.add(user)
        await db.flush()
    else:
        user.email = token_result.user_info.email
        user.full_name = token_result.user_info.full_name
        user.picture_url = token_result.user_info.picture_url

    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user.id))
    oauth_token = result.scalar_one_or_none()

    access_token_enc = token_crypto.encrypt(token_result.access_token)
    refresh_token_enc = (
        token_crypto.encrypt(token_result.refresh_token) if token_result.refresh_token else None
    )

    if oauth_token is None:
        oauth_token = OAuthToken(
            user_id=user.id,
            access_token_enc=access_token_enc,
            refresh_token_enc=refresh_token_enc,
            scope=token_result.scope,
            token_expiry=token_result.token_expiry,
        )
        db.add(oauth_token)
    else:
        oauth_token.access_token_enc = access_token_enc
        if refresh_token_enc:
            oauth_token.refresh_token_enc = refresh_token_enc
        oauth_token.scope = token_result.scope
        oauth_token.token_expiry = token_result.token_expiry

    await db.commit()

    session_token = create_session_token(user.id)

    redirect = RedirectResponse(url=settings.FRONTEND_URL, status_code=status.HTTP_302_FOUND)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE)
    redirect.delete_cookie(_OAUTH_CODE_VERIFIER_COOKIE)
    redirect.set_cookie(
        settings.SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE_SECONDS,
    )
    return redirect


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return {"status": "ok"}


@router.get("/timezones", response_model=list[str])
async def list_timezones() -> list[str]:
    """The canonical IANA timezone list the backend validates PATCH /auth/me against —
    served from here (rather than the frontend using the browser's own Intl.supportedValuesOf)
    so the two can never drift apart. Different tzdata builds disagree on which deprecated
    backward-compat aliases (e.g. Asia/Calcutta) exist; the frontend must offer only names
    this exact backend instance's zoneinfo actually has."""
    return sorted(available_timezones())


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    update: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if update.llm_provider is not None:
        if update.llm_provider not in settings.AVAILABLE_LLM_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported llm_provider. Available: {settings.AVAILABLE_LLM_PROVIDERS}",
            )
        current_user.llm_provider = update.llm_provider

    if update.timezone is not None:
        if update.timezone not in available_timezones():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown timezone: {update.timezone!r}. Use an IANA timezone name, e.g. 'America/New_York'.",
            )
        current_user.timezone = update.timezone

    await db.commit()
    return current_user
