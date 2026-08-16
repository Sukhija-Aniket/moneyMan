# Pulsar topic names. Two stages, each with its own job/event topic pair:
#
#   1. Fetch stage: backend publishes GMAIL_SYNC_JOBS (one message per sync request — plain
#      "Sync now" or a date range). The worker's fetch consumer lists Gmail, runs Gate 1,
#      writes raw_emails, and publishes one EMAIL_EXTRACTION_JOBS message per candidate email
#      — then reports GMAIL_SYNC_FETCH_EVENTS once (fetch-stage counters + total_candidates).
#
#   2. Extraction stage: the worker's extraction consumer picks up EMAIL_EXTRACTION_JOBS one
#      at a time — classify, extract, dedupe-check, write Transaction — and acks only after
#      that email's outcome is committed. A crash before ack means Pulsar redelivers that
#      exact message, so a single email's failure never gets silently lost (the bug this
#      whole split exists to fix). Each outcome is reported on EMAIL_EXTRACTION_EVENTS.
#
# The backend is the only writer of sync_triggers: it increments processed_candidates as
# EMAIL_EXTRACTION_EVENTS arrive and flips the trigger to success once
# processed_candidates == total_candidates.

GMAIL_SYNC_JOBS_TOPIC = "persistent://public/default/gmail-sync-jobs"
GMAIL_SYNC_FETCH_EVENTS_TOPIC = "persistent://public/default/gmail-sync-fetch-events"

EMAIL_EXTRACTION_JOBS_TOPIC = "persistent://public/default/email-extraction-jobs"
EMAIL_EXTRACTION_EVENTS_TOPIC = "persistent://public/default/email-extraction-events"

GMAIL_SYNC_JOBS_SUBSCRIPTION = "gmail-sync-worker"
GMAIL_SYNC_FETCH_EVENTS_SUBSCRIPTION = "gmail-sync-backend"

EMAIL_EXTRACTION_JOBS_SUBSCRIPTION = "email-extraction-worker"
EMAIL_EXTRACTION_EVENTS_SUBSCRIPTION = "email-extraction-backend"
