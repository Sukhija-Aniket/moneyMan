# Moneyman TODO

Phase 1 vertical slice is built and running locally (backend on :8000, frontend on :3000,
Postgres via the `moneyman-pg` docker container). Everything below is placeholder/dummy config
or Phase 2/3 work not yet started.

## Next up: real config (tomorrow)

- [ ] **Google Cloud project + OAuth client**
  - Create a GCP project, enable the Gmail API.
  - Create an OAuth 2.0 Client ID (Web application).
  - Local redirect URI: `http://localhost:8000/auth/google/callback`.
  - Add `gmail.readonly` scope on the OAuth consent screen — this is a *restricted scope*, so real
    (non-test) users beyond a small test-user allowlist will eventually need Google's CASA
    security assessment before going live. Add self as a test user for now.
  - Put real `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` into `backend/.env` (currently dummy
    values).
- [ ] **Anthropic API key**
  - Replace dummy `ANTHROPIC_API_KEY` in `backend/.env` with a real key.
  - Sanity-check `GMAIL_CLASSIFICATION_MODEL` / `GMAIL_EXTRACTION_MODEL` env vars still point at
    valid, available model names at the time.
- [ ] **Generate real secrets for prod** (local `.env` already has generated values, but they're
      local-only — don't reuse across environments):
  - `TOKEN_ENCRYPTION_KEY` (Fernet key)
  - `SESSION_SECRET`
- [ ] **End-to-end smoke test** once the above are in place:
  - Sign in with Google from the frontend, confirm `gmail.readonly` consent screen appears.
  - Click "Sync now", confirm real transaction emails get classified/extracted into the
    transactions table.
  - Spot-check a few extracted transactions against the source emails for accuracy.

## Two-environment config (local vs. prod)

- Local: `backend/.env` (`DATABASE_URL` → local Postgres, `FRONTEND_URL=http://localhost:3000`,
  `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback`) and
  `frontend/.env.local` (`VITE_API_BASE_URL=http://localhost:8000`).
- Prod: separate env values pointing at deployed URLs — update `FRONTEND_URL`,
  `GOOGLE_REDIRECT_URI`, `DATABASE_URL`, and `VITE_API_BASE_URL` accordingly. Add the prod
  redirect URI as an additional authorized redirect URI on the same OAuth client (or a separate
  prod OAuth client, if preferred — decide when we get there).
- Nothing in the code is hardcoded to a port/host; all of this is env-driven already.

## Phase 2 (real-time ingestion) — not started

- [ ] GCP Pub/Sub topic + push subscription for Gmail `watch()` notifications.
- [ ] `POST /webhooks/pubsub` endpoint with OIDC token verification.
- [ ] `arq` + Redis background worker (move classify/extract off the synchronous request path).
- [ ] Switch from `messages.list` (Phase 1) to `history.list`-based incremental sync using the
      existing `gmail_watch_state` table (already created by the migration, unused so far).
- [ ] Daily watch-renewal cron (watches expire silently after ~7 days) + hourly reconciliation
      sweep safety net.

## Phase 3 (polish/hardening) — not started

- [ ] Postgres Row-Level Security policies (currently app-layer `user_id` scoping only).
- [ ] Rate limiting (`slowapi`) on public endpoints + token-bucket throttling on Gmail/Claude calls.
- [ ] Swap `cryptography.fernet` token encryption for Cloud KMS envelope encryption.
- [ ] Multi-currency aggregation — `/summary/overview` currently sums naively across currencies
      (labeled `"USD"` as a placeholder); needs a product decision (per-currency breakdown vs.
      FX-normalized total).
- [ ] Digest/multi-transaction emails — schema currently assumes one email → at most one
      transaction.
- [ ] Duplicate transaction detection (e.g. "pending" vs "posted" emails for the same charge).
- [ ] Account/issuer entity resolution (fuzzy-match "Chase Sapphire" vs "CHASE CREDIT CARD" etc.
      to avoid duplicate `accounts` rows).
- [ ] User-editable `category_rules` for auto-categorization.
- [ ] Data retention policy for `raw_emails.body_text` (purge after successful extraction).
- [ ] Observability: per-user ingestion health, LLM cost tracking.

## Reference

- Full architecture plan: `~/.claude/plans/fuzzy-tumbling-moon.md`
- Backend setup details: `backend/README.md`
- If any tooling needs Docker in this environment, use
  `/Users/asukhija/programs/scripts/dockr.sh` instead of the raw `docker` binary.
