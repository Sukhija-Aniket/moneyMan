FROM python:3.12-slim

WORKDIR /app

# See backend/Dockerfile — same corporate-proxy CA note applies here (pip installing from
# PyPI below, and the worker's own Gmail API calls at runtime).
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY infra/certs/corporate-ca.pem /usr/local/share/ca-certificates/corporate-ca.crt
RUN if [ -s /usr/local/share/ca-certificates/corporate-ca.crt ]; then update-ca-certificates; fi

# See backend/Dockerfile — same HTTPLIB2_CA_CERTS/REQUESTS_CA_BUNDLE/SSL_CERT_FILE overrides
# for the Debian container path. The worker additionally needs SSL_CERT_FILE because its
# extraction stage calls the Anthropic SDK, which goes through httpx — a third HTTP stack
# (distinct from httplib2 and requests) that verifies against certifi's bundle by default;
# SSL_CERT_FILE is the standard OpenSSL-level override httpx's ssl context construction
# honors.
ENV HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY shared /shared
COPY worker/pyproject.toml /app/
COPY worker/worker /app/worker

RUN pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt /shared \
    && pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt -e .

CMD ["python", "-m", "worker.main"]
