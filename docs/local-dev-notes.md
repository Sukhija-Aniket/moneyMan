# Local dev environment quirks

Notes on environment-specific issues hit while running this app locally, and what fixed them.
Kept separate from `todo.md` since these are durable facts about the dev machine/network, not
open tasks.

## Corporate TLS-inspecting proxy (Zscaler) breaks Gmail API calls

**Symptom:** `POST /gmail/sync` fails with:

```
Failed to list Gmail messages: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate (_ssl.c:1000)
```

**Root cause:** This machine's network traffic (at least to `www.googleapis.com`) is intercepted
by a corporate Zscaler proxy that re-signs TLS connections with its own intermediate/root CA
(confirmed via `openssl s_client -connect www.googleapis.com:443 -showcerts`, which showed the
served cert issued by `Zscaler Intermediate Root CA`, not a real Google/GTS CA).

- macOS's system trust store (Keychain) has the Zscaler root installed, so anything using the
  OS trust store directly (Python's `ssl.create_default_context()` with no args) verifies fine.
- `googleapiclient` (used by `app/services/gmail_client.py` for all Gmail API calls) uses
  `httplib2` under the hood, which verifies against **`certifi`'s bundled public-CA list** by
  default — a curated list of public CAs that deliberately excludes private/corporate CAs like
  Zscaler's. That's why this call specifically fails while other HTTPS traffic on the machine
  (e.g. `pip install`, browser traffic) may work fine.

**Fix:** `httplib2` honors an `HTTPLIB2_CA_CERTS` env var (see `httplib2/certs.py`) that
overrides the certifi lookup. `app/services/gmail_client.py` sets this at import time to
`/etc/ssl/certs/ca-bundle.pem` — the OS-level CA bundle, which is kept in sync with
proxy-injected roots (confirmed present there) — via `os.environ.setdefault(...)`, so it only
applies if not already set by the shell/deployment environment.

If this ever needs re-diagnosing on a different machine/network: re-run the `openssl s_client`
command above against `www.googleapis.com` and check the `issuer=` line. If it's not a real
Google/GTS/DigiCert root, you're behind a TLS-inspecting proxy and this same class of fix
applies (point the failing library's cert lookup at the OS trust store instead of `certifi`).

## `oauthlib` scope-mismatch hard failure

**Symptom:** OAuth callback 500s with:

```
Warning: Scope has changed from "... gmail.readonly ..." to "..." (without gmail.readonly)
```

raised as `oauthlib.oauth2.rfc6749.errors.Warning` inside `parse_token_response`.

**Root cause:** `oauthlib` treats any mismatch between the scopes requested at
`/auth/google/login` and the scopes Google actually grants back at the token exchange as fatal
by default (`raise w` in `oauthlib/oauth2/rfc6749/parameters.py`). Google can legitimately grant
a narrower or reordered scope set (e.g. right after a scope is newly added to the OAuth consent
screen, before the change fully propagates) — this shouldn't crash the app.

**Fix:** `app/services/google_oauth.py` sets `OAUTHLIB_RELAX_TOKEN_SCOPE=1` at import time,
which is oauthlib's documented escape hatch for this exact case.

## PKCE `code_verifier` lost between login and callback

**Symptom:** OAuth callback 500s with `oauthlib.oauth2.rfc6749.errors.InvalidGrantError:
(invalid_grant) Missing code verifier`.

**Root cause:** `google_auth_oauthlib.flow.Flow` auto-generates a PKCE `code_verifier` and
stores it **on the `Flow` instance** when `authorization_url()` is called. `/auth/google/login`
and `/auth/google/callback` are separate HTTP requests, each building a fresh `Flow` via
`build_flow()` — so the callback's `Flow` never has the verifier the login step generated.

**Fix:** `get_authorization_url()` now returns `(auth_url, code_verifier)`; `/auth/google/login`
stores the verifier in an `httponly` cookie (`oauth_code_verifier`, mirroring the existing
`oauth_state` cookie pattern) and `/auth/google/callback` passes it back into
`build_flow(code_verifier=...)` before exchanging the code.

## Google OAuth consent screen "Internal" user type blocks personal Gmail accounts

**Symptom:** Google sign-in fails immediately with "You can't sign in because this app sent an
invalid request," with no further detail, even though redirect URI / scopes / client type all
looked correct.

**Root cause:** The OAuth consent screen's **User Type** was set to **Internal**, which only
allows sign-in from accounts inside the same Google Workspace org as the GCP project. There is
no allowlist for personal `@gmail.com` accounts under Internal — it's not a matter of adding a
test user, Internal has no such mechanism at all.

**Fix:** Switched User Type to **External**, which puts the app in **Testing** publish status
and unlocks the **Test users** allowlist (up to 100 accounts) — added the personal test Gmail
account there. No CASA security assessment is needed in Testing status; that's only required
before moving to **In Production** for public launch (see `todo.md`).

## Expired Gmail OAuth access token never refreshed before sync

**Symptom:** `POST /gmail/sync` intermittently fails once enough time has passed since login
(Google access tokens expire in ~1 hour).

**Root cause:** `sync_now` in `app/api/routes/gmail.py` read `oauth_token.access_token_enc`
directly and called the Gmail API with it, with no check against `oauth_token.token_expiry` and
no call to the already-existing (but previously unused) `google_oauth.refresh_access_token()`.

**Fix:** `sync_now` now checks `token_expiry` against the current time before using the access
token; if expired, it decrypts the stored refresh token, calls `refresh_access_token()`, and
persists the new access token + expiry before proceeding.

## Dry-run mode for exercising the sync pipeline without a real Anthropic key

`GMAIL_SYNC_DRY_RUN=true` (see `.env`, `app/config.py`) makes `classification_service.py` and
`extraction_service.py` return canned results instead of calling the Anthropic API. This lets
the Gmail fetch → Gate 1 filter → store pipeline be exercised end-to-end (real Gmail API calls,
real DB writes) without needing `ANTHROPIC_API_KEY` set to a real key. Every email that passes
the Gate 1 heuristic becomes an identical synthetic "Dry Run Merchant / $42.00 debit"
transaction — this validates plumbing, not classification/extraction quality. Turn off before
testing real extraction behavior.
