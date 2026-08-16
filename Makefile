# Local dev orchestration for the full moneyman stack (postgres, pulsar, backend, worker,
# frontend). See docs/design.md for the Pulsar topic/subscription contract these targets set
# up, and docs/local-dev-notes.md for environment-specific quirks.
#
# Uses the dockr.sh wrapper (see root README.md "Notes for this environment") rather than the
# raw docker binary, so CLI-plugin discovery (docker compose) resolves correctly here.
# Override DOCKER=... if that wrapper isn't present in your environment.
DOCKER ?= /Users/asukhija/programs/scripts/dockr.sh
COMPOSE := $(DOCKER) compose -f infra/docker-compose.yml

TOPICS := \
	persistent://public/default/gmail-sync-jobs \
	persistent://public/default/email-extraction-jobs \
	persistent://public/default/email-extraction-events \
	persistent://public/default/gmail-sync-fetch-events

SUBSCRIPTIONS := \
	gmail-sync-jobs:gmail-sync-worker \
	email-extraction-jobs:email-extraction-worker \
	email-extraction-events:gmail-sync-worker \
	gmail-sync-fetch-events:gmail-sync-backend

CERT_DIR := infra/certs
CERT_FILE := $(CERT_DIR)/corporate-ca.pem

.PHONY: setup start stop down logs clean certs

## Exports this machine's corporate TLS-inspecting proxy root CA (if any — see
## docs/local-dev-notes.md's Zscaler note) so backend/worker image builds can trust it when
## pip installs from PyPI. Gitignored (*.pem), regenerated per machine. A build on a network
## with no such proxy just gets an empty file, which the Dockerfiles skip installing.
certs:
	@mkdir -p $(CERT_DIR)
	@security find-certificate -a -c "Zscaler Root CA" -p /Library/Keychains/System.keychain > $(CERT_FILE) 2>/dev/null || true
	@if [ -s $(CERT_FILE) ]; then \
		echo "Exported corporate proxy root CA to $(CERT_FILE)"; \
	else \
		echo "No corporate proxy root CA found — $(CERT_FILE) left empty (fine on an unproxied network)."; \
	fi

## Starts Pulsar (if not already running) and creates the topics/subscriptions this app
## needs. Safe to re-run — pulsar-admin create is a no-op if a topic/subscription already
## exists.
setup:
	$(COMPOSE) up -d pulsar
	@echo "Waiting for Pulsar to become healthy..."
	@until $(DOCKER) inspect --format='{{.State.Health.Status}}' $$($(COMPOSE) ps -q pulsar) 2>/dev/null | grep -q healthy; do sleep 2; done
	@for topic in $(TOPICS); do \
		echo "Creating topic $$topic"; \
		$(COMPOSE) exec -T pulsar bin/pulsar-admin topics create-partitioned-topic --partitions 1 $$topic 2>/dev/null || \
		$(COMPOSE) exec -T pulsar bin/pulsar-admin topics create $$topic 2>/dev/null || true; \
	done
	@for pair in $(SUBSCRIPTIONS); do \
		topic=$${pair%%:*}; sub=$${pair##*:}; \
		echo "Creating subscription $$sub on $$topic"; \
		$(COMPOSE) exec -T pulsar bin/pulsar-admin topics create-subscription \
			--subscription $$sub persistent://public/default/$$topic 2>/dev/null || true; \
	done
	@echo "Pulsar topics/subscriptions ready."

## Builds and starts the full stack (postgres, pulsar, backend, worker, frontend) in the
## foreground. Run `make setup` first if this is a fresh Pulsar instance.
start: certs
	$(COMPOSE) up --build

## Starts the full stack in the background.
up: certs
	$(COMPOSE) up --build -d

## Stops all containers without removing them.
stop:
	$(COMPOSE) stop

## Stops and removes all containers (keeps named volumes — postgres/pulsar data survives).
down:
	$(COMPOSE) down

## Tails logs from all services.
logs:
	$(COMPOSE) logs -f

## Stops and removes containers AND volumes — wipes Postgres data and Pulsar state.
clean:
	$(COMPOSE) down -v
