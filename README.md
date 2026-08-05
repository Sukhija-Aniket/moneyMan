# Moneyman

A multi-user transaction tracker: sign in with Google, grant read access to your Gmail, and
Moneyman turns your bank/card transaction emails into a single dashboard — total spend, income,
and breakdowns by category, account/card, and bank — plus CSV export.

This is the **Phase 1 vertical slice** (manual sync, no push notifications yet). See the full
architecture plan at `~/.claude/plans/fuzzy-tumbling-moon.md` for the complete design, including
Phase 2 (Gmail push notifications via Pub/Sub + background workers) and Phase 3 (polish,
hardening, multi-currency, rate limiting).

## Repo layout

```
moneyman/
├── backend/    FastAPI + Postgres + Google OAuth + Claude-based extraction (see backend/README.md)
├── frontend/   React + Vite dashboard (login, transactions, charts, CSV export)
├── infra/      (Phase 2+) Terraform for GCP: Cloud Run, Cloud SQL, Pub/Sub, Secret Manager
└── docs/
```

## Quick start (local dev)

You'll need: Python 3.12, Node 18+, a local Postgres instance, a Google Cloud OAuth client, and
an Anthropic API key.

**1. Start Postgres** (if using Docker in this environment, use the `dockr.sh` wrapper instead of
the raw `docker` CLI — see `backend/README.md` for the exact command).

**2. Backend:**

```bash
cd backend
python3.12 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # fill in DATABASE_URL, GOOGLE_CLIENT_ID/SECRET, ANTHROPIC_API_KEY, etc.
./.venv/bin/alembic upgrade head
./.venv/bin/uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`. Full details, Google Cloud setup steps, and Phase 1
deviations/limitations are in `backend/README.md`.

**3. Frontend:**

```bash
cd frontend
cp .env.example .env.local   # VITE_API_BASE_URL, defaults to http://localhost:8000
npm install
npm run dev
```

Visit `http://localhost:5173`, sign in with Google, click **Sync now** on the dashboard to pull
and extract recent transaction emails.

## What's implemented (Phase 1)

- Google sign-in doubling as `gmail.readonly` consent.
- Encrypted OAuth token storage (Fernet — a stand-in for Cloud KMS envelope encryption, see plan).
- Manual "Sync now": fetches recent Gmail messages, runs a cheap heuristic filter + two-stage
  Claude pipeline (Haiku classification → Sonnet structured extraction), stores transactions with
  confidence-based auto-accept / needs-review / discard.
- Dashboard: totals, category/account/bank breakdowns, monthly trend, transactions table with
  filters, a review queue for low-confidence extractions, and CSV export.

## What's not yet built (see plan for Phase 2/3)

- Real-time ingestion via Gmail push notifications (`watch()` + Pub/Sub) — Phase 1 requires
  clicking "Sync now".
- Background job queue (`arq`/Redis) — Phase 1 calls Gmail/Claude synchronously inline.
- Postgres Row-Level Security, rate limiting, KMS-based token encryption, multi-currency
  normalization, digest-email (multi-transaction-per-email) support.
- Google OAuth app verification / CASA security assessment — required before real (non-test)
  users beyond a small allowlist can use Gmail access; has real lead time, start in parallel with
  further engineering.

## Notes for this environment

If any tooling needs to invoke Docker, use `/Users/asukhija/programs/scripts/dockr.sh` rather than
the `docker` binary directly (it forwards to the real docker binary but resolves CLI-plugin
discovery correctly here).
