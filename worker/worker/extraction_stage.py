import asyncio
import logging
import uuid

from sqlalchemy import select

from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import AsyncSessionLocal
from moneyman_shared.messaging.client import get_pulsar_client
from moneyman_shared.messaging.schemas import EmailExtractionEvent, EmailExtractionJob
from moneyman_shared.messaging.topics import (
    EMAIL_EXTRACTION_EVENTS_TOPIC,
    EMAIL_EXTRACTION_JOBS_SUBSCRIPTION,
    EMAIL_EXTRACTION_JOBS_TOPIC,
)
from moneyman_shared.services.gmail_sync import extract_one_email

logger = logging.getLogger(__name__)

# Worker 2 (extraction stage) — see docs/design.md "Stage 2: Extraction". Consumes one
# EmailExtractionJob at a time, classifies/extracts/writes a Transaction for that single
# email, and only acks after both the DB commit and the EmailExtractionEvent publish
# succeed — a crash between receiving and acking means Pulsar redelivers this exact
# message, so a single email's failure can never silently vanish from the count the fetch
# stage is waiting on. extract_one_email is idempotent per raw_email_id, so redelivery is
# always safe to reprocess.

_stop = False


def _receive_one(consumer, timeout_millis: int):
    try:
        return consumer.receive(timeout_millis=timeout_millis)
    except Exception:
        return None


async def _process_job(job: EmailExtractionJob) -> str:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == uuid.UUID(job.user_id)))
        user = result.scalar_one_or_none()
        if user is None:
            return "extract_failed"
        return await extract_one_email(db, user, uuid.UUID(job.raw_email_id))


async def run_extraction_stage_forever() -> None:
    client = get_pulsar_client()
    jobs_consumer = client.subscribe(EMAIL_EXTRACTION_JOBS_TOPIC, EMAIL_EXTRACTION_JOBS_SUBSCRIPTION)
    events_producer = client.create_producer(EMAIL_EXTRACTION_EVENTS_TOPIC)

    logger.info("Extraction stage started, listening on %s", EMAIL_EXTRACTION_JOBS_TOPIC)

    try:
        while not _stop:
            msg = await asyncio.to_thread(_receive_one, jobs_consumer, 2000)
            if msg is None:
                continue

            try:
                job = EmailExtractionJob.model_validate_json(msg.data())
                outcome = await _process_job(job)
                event = EmailExtractionEvent(
                    segment_id=job.segment_id, raw_email_id=job.raw_email_id, outcome=outcome
                )
                events_producer.send(event.model_dump_json().encode("utf-8"))
                jobs_consumer.acknowledge(msg)
                logger.info(
                    "Extraction stage processed email %s (segment %s): %s",
                    job.raw_email_id,
                    job.segment_id,
                    outcome,
                )
            except Exception:
                logger.exception("Failed to process email-extraction-jobs message")
                jobs_consumer.negative_acknowledge(msg)
    finally:
        events_producer.close()
        jobs_consumer.close()
