FROM python:3.12-slim

WORKDIR /app

# Corporate TLS-inspecting proxies (see docs/local-dev-notes.md) re-sign certs with a private
# root — both pip (installing from PyPI below) and googleapiclient's httplib2 (calling the
# Gmail API at runtime) fail TLS verification against such a proxy unless that root is
# trusted. `make certs` exports it (if present on the host) to infra/certs/corporate-ca.pem,
# gitignored — an empty file here is a normal no-op on an unproxied network.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY infra/certs/corporate-ca.pem /usr/local/share/ca-certificates/corporate-ca.crt
RUN if [ -s /usr/local/share/ca-certificates/corporate-ca.crt ]; then update-ca-certificates; fi

# shared/services/gmail_client.py defaults HTTPLIB2_CA_CERTS to the Homebrew-on-macOS path
# (/etc/ssl/certs/ca-bundle.pem) via setdefault — override it here to Debian's actual
# update-ca-certificates output path so the Gmail API client (httplib2) trusts the same
# bundle at container runtime. REQUESTS_CA_BUNDLE covers the other HTTP stack in play here:
# google_auth_oauthlib's token exchange (services/google_oauth.py) goes through `requests`,
# which verifies against certifi's bundled public-CA list by default — unlike httplib2, it
# isn't controlled by HTTPLIB2_CA_CERTS, so it needs its own override to trust the same
# corporate-proxy root baked in above.
ENV HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
# The plain "Sync now" path calls the Anthropic SDK too (via httpx, a third HTTP stack) —
# SSL_CERT_FILE is the standard OpenSSL-level override httpx's ssl context construction
# honors, distinct from both HTTPLIB2_CA_CERTS and REQUESTS_CA_BUNDLE above.
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY shared /shared
COPY backend/pyproject.toml backend/alembic.ini /app/
COPY backend/alembic /app/alembic
COPY backend/app /app/app

# -e (editable) on /shared too: a plain (non-editable) install copies files into
# site-packages at build time and never looks at /shared again, which silently defeats the
# /shared bind mount in infra/docker-compose.yml -- edits under shared/ would be invisible
# to the running app even with --reload watching that path.
RUN pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt -e /shared \
    && pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt -e .

EXPOSE 8000

# --reload-dir /shared: shared/ is bind-mounted separately from app/ in dev (see
# infra/docker-compose.yml) and uvicorn's default reload watch is CWD-only, so it needs to
# be told about that second tree explicitly to pick up moneyman_shared edits.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app --reload-dir /shared"]
