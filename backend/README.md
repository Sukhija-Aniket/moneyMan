# Moneyman Backend — Phase 1

FastAPI backend for the Moneyman multi-user Gmail transaction tracker. This is the Phase 1
vertical slice: Google sign-in, encrypted token storage, a manual "Sync now" endpoint that
classifies and extracts transactions from recent Gmail messages via Claude, and read/summary
endpoints for the dashboard.

See `/Users/asukhija/.claude/plans/fuzzy-tumbling-moon.md` for the full architecture plan.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + Alembic, target DB Postgres (asyncpg driver)
- `google-auth-oauthlib` + `google-api-python-client` for Google OAuth and Gmail API
- `anthropic` SDK for the two-stage classification/extraction pipeline
- `cryptography.fernet` for at-rest token encryption (Phase 1 stand-in for Cloud KMS)
- `python-jose` for signed session cookies (HS256 JWT)

## Local setup

1. Create a virtualenv with Python 3.11+ (3.12 recommended — some dependencies lag on 3.13/3.14):

   ```bash
   python3.12 -m venv .venv
   ./.venv/bin/python -m pip install --upgrade pip
   ./.venv/bin/python -m pip install -e ".[dev]"
   ```

2. Copy `.env.example` to `.env` and fill in real values (Google OAuth client, Anthropic API key,
   a generated Fernet key, a random session secret). `pydantic-settings` loads `.env` automatically.

3. Start a local Postgres. If you use Docker, this environment's `docker` CLI resolves plugins
   incorrectly — use the wrapper at `/Users/asukhija/programs/scripts/dockr.sh` instead of `docker`
   directly, e.g.:

   ```bash
   dockr.sh run -d --name moneyman-pg \
     -e POSTGRES_USER=moneyman -e POSTGRES_PASSWORD=moneyman -e POSTGRES_DB=moneyman \
     -p 5432:5432 postgres:16-alpine
   ```

4. Run migrations:

   ```bash
   ./.venv/bin/alembic upgrade head
   ```

5. Start the API:

   ```bash
   ./.venv/bin/uvicorn app.main:app --reload
   ```

   Visit `http://localhost:8000/docs` for the interactive OpenAPI docs, or `/health` for a
   liveness check.

## Google Cloud setup (required for real OAuth/Gmail testing)

1. Create a GCP project and enable the Gmail API.
2. Create an OAuth 2.0 Client ID (Web application) with redirect URI
   `http://localhost:8000/auth/google/callback` (or your deployed URL).
3. Add the `gmail.readonly` scope on the OAuth consent screen. Because `gmail.readonly` is a
   restricted scope, real (non-test) users beyond a small allowlist require Google's CASA
   security assessment before going live — start that process early (plan §10, risk 1).
4. Put the client ID/secret into `.env`.

## Anthropic setup

Set `ANTHROPIC_API_KEY` in `.env`. The Phase 1 pipeline calls the Anthropic API directly and
synchronously (inline in the request handler) — no queue/worker yet, so `POST /gmail/sync` will
block for the duration of the sync (bounded by `GMAIL_SYNC_MAX_RESULTS`, default 25 messages).

## Verifying the build without live credentials

```bash
DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db" \
GOOGLE_CLIENT_ID=dummy GOOGLE_CLIENT_SECRET=dummy \
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback \
ANTHROPIC_API_KEY=dummy \
TOKEN_ENCRYPTION_KEY="$(./.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
SESSION_SECRET=dummy-secret \
./.venv/bin/python -c "from app.main import app; print('import OK')"
```

This confirms the app constructs cleanly without a live DB connection (DB calls only happen
per-request, not at import time).

## Deviations from the plan / notes

- **Phase 2/3 features are intentionally not implemented**, per the plan's phased build order:
  - Pub/Sub push notifications, `users.watch()`, `/webhooks/pubsub` (Phase 2)
  - `arq` + Redis background workers — Phase 1 calls Gmail/Claude synchronously inline in the
    request handler for `POST /gmail/sync`
  - `history.list`-based incremental sync — Phase 1 uses a simple `messages.list` fetch of the
    most recent N inbox messages
  - Daily watch-renewal cron, reconciliation sweep (Phase 2)
  - `category_rules` / auto-categorization, "needs review" queue UI, RLS policies, `slowapi`
    rate limiting, per-user LLM cost tracking (Phase 3)
  - The `gmail_watch_state` table is created by the initial migration (per plan §2 / §9.5) but is
    never populated or queried in Phase 1 code.
- **Postgres Row-Level Security (RLS)** is not configured. Multi-tenancy is enforced only at the
  application query layer (every query filters by `user_id` derived from the session, never from
  a request parameter) — the plan's "defense in depth" RLS layer is a Phase 3 hardening item.
- **Fernet vs. Cloud KMS**: `app/services/token_crypto.py` uses `cryptography.fernet.Fernet` with
  a single symmetric key from `TOKEN_ENCRYPTION_KEY`. This is a placeholder for the envelope
  encryption via Cloud KMS described in the plan for production — same call sites, swap the
  implementation later.
- **Digest/multi-transaction emails**: not handled — the schema and extraction pipeline assume
  one email maps to at most one transaction, per the plan's stated v1 assumption (risk 5).
- **Multi-currency aggregation**: `/summary/*` endpoints sum `amount` directly per currency
  bucket where grouped, but `/summary/overview` sums across all currencies naively (labeled
  `"currency": "USD"` as a placeholder) — the plan flags this as an open product decision
  (risk 4) still needing FX-normalization or per-currency breakdown before it's correct at scale.

## What needs real credentials to test end-to-end

- A real Google Cloud OAuth client + `gmail.readonly` consent screen to exercise
  `/auth/google/login` → `/auth/google/callback` and get a real `refresh_token`.
- A real Gmail inbox with actual bank/card notification emails to exercise `POST /gmail/sync`
  meaningfully (Gate 1 heuristic, Stage A classification, Stage B extraction).
- A real `ANTHROPIC_API_KEY` for the classification (`claude-haiku-4-5`) and extraction
  (`claude-sonnet-4-5`) calls.
- A real Postgres instance for anything beyond the import-only smoke test above.
