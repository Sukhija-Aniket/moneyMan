import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import select

from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import AsyncSessionLocal
from moneyman_shared.messaging.client import get_pulsar_client
from moneyman_shared.messaging.schemas import GmailSyncEvent, GmailSyncJob
from moneyman_shared.messaging.topics import (
    GMAIL_SYNC_EVENTS_TOPIC,
    GMAIL_SYNC_JOBS_SUBSCRIPTION,
    GMAIL_SYNC_JOBS_TOPIC,
)
from moneyman_shared.services.gmail_sync import GmailSyncError, run_gmail_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _process_job(job: GmailSyncJob) -> GmailSyncEvent:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == uuid.UUID(job.user_id)))
        user = result.scalar_one_or_none()
        if user is None:
            return GmailSyncEvent(trigger_id=job.trigger_id, status="failed", error="User not found.")

        try:
            counters = await run_gmail_sync(
                db, user, date.fromisoformat(job.date_from), date.fromisoformat(job.date_to)
            )
        except GmailSyncError as exc:
            logger.warning("Sync job %s failed: %s", job.trigger_id, exc)
            return GmailSyncEvent(trigger_id=job.trigger_id, status="failed", error=str(exc))
        except Exception as exc:  # unexpected — still report failure, don't crash the worker
            logger.exception("Sync job %s failed unexpectedly", job.trigger_id)
            return GmailSyncEvent(trigger_id=job.trigger_id, status="failed", error=str(exc))

        return GmailSyncEvent(trigger_id=job.trigger_id, status="success", **counters.as_dict())


def _receive_one(consumer, timeout_millis: int):
    try:
        return consumer.receive(timeout_millis=timeout_millis)
    except Exception:
        return None


async def run_forever() -> None:
    client = get_pulsar_client()
    consumer = client.subscribe(GMAIL_SYNC_JOBS_TOPIC, GMAIL_SYNC_JOBS_SUBSCRIPTION)
    producer = client.create_producer(GMAIL_SYNC_EVENTS_TOPIC)

    logger.info("Worker started, listening on %s", GMAIL_SYNC_JOBS_TOPIC)

    try:
        while True:
            msg = await asyncio.to_thread(_receive_one, consumer, 2000)
            if msg is None:
                continue

            try:
                job = GmailSyncJob.model_validate_json(msg.data())
                logger.info("Processing sync job %s (%s -> %s)", job.trigger_id, job.date_from, job.date_to)
                event = await _process_job(job)
                producer.send(event.model_dump_json().encode("utf-8"))
                consumer.acknowledge(msg)
                logger.info("Completed sync job %s: %s", job.trigger_id, event.status)
            except Exception:
                logger.exception("Failed to process gmail-sync-jobs message")
                consumer.negative_acknowledge(msg)
    finally:
        producer.close()
        consumer.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
