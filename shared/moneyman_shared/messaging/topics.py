# Pulsar topic names. Two stages, each with its own job/event topic pair:
#
#   1. Fetch stage: backend computes unsynced gap segments for a requested range and
#      publishes one GMAIL_SYNC_JOBS message per segment. The fetch stage lists Gmail
#      messages for that segment, runs Gate 1, writes raw_emails, and publishes one
#      EMAIL_EXTRACTION_JOBS message per candidate email — then, once every one of that
#      segment's candidates has a terminal EMAIL_EXTRACTION_EVENTS reply, reports one
#      GMAIL_SYNC_FETCH_EVENTS message (aggregated counters) for the whole segment.
#
#   2. Extraction stage: consumes EMAIL_EXTRACTION_JOBS one at a time — classify, extract,
#      dedupe-check, write Transaction — and acks only after that email's outcome is
#      committed. A crash before ack means Pulsar redelivers that exact message, so a single
#      email's failure never gets silently lost. Each outcome is reported back to the fetch
#      stage (not the backend) on EMAIL_EXTRACTION_EVENTS.
#
# The backend is the only writer of sync_requests/sync_segments/synced_ranges: it marks a
# segment terminal on GMAIL_SYNC_FETCH_EVENTS_TOPIC and, on success, merge-inserts a
# synced_ranges row for that segment's exact range.

GMAIL_SYNC_JOBS_TOPIC = "persistent://public/default/gmail-sync-jobs"
EMAIL_EXTRACTION_JOBS_TOPIC = "persistent://public/default/email-extraction-jobs"
EMAIL_EXTRACTION_EVENTS_TOPIC = "persistent://public/default/email-extraction-events"
GMAIL_SYNC_FETCH_EVENTS_TOPIC = "persistent://public/default/gmail-sync-fetch-events"

GMAIL_SYNC_JOBS_SUBSCRIPTION = "gmail-sync-worker"
EMAIL_EXTRACTION_JOBS_SUBSCRIPTION = "email-extraction-worker"
EMAIL_EXTRACTION_EVENTS_SUBSCRIPTION = "gmail-sync-worker"
GMAIL_SYNC_FETCH_EVENTS_SUBSCRIPTION = "gmail-sync-backend"
