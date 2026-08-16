import asyncio
import logging
import uuid

from moneyman_shared.db.session import AsyncSessionLocal
from moneyman_shared.messaging.client import get_pulsar_client
from moneyman_shared.messaging.schemas import GmailSyncEvent
from moneyman_shared.messaging.topics import GMAIL_SYNC_EVENTS_SUBSCRIPTION, GMAIL_SYNC_EVENTS_TOPIC

from app.services import sync_trigger_service

logger = logging.getLogger(__name__)

_stop = False


def _receive_one(consumer, timeout_millis: int):
    """Pulsar's Python client is synchronous — run receive() in a thread so it doesn't
    block the asyncio event loop the rest of the backend runs on."""
    try:
        return consumer.receive(timeout_millis=timeout_millis)
    except Exception:
        return None


async def consume_sync_events_forever() -> None:
    """Background task (started at app startup, see main.py) that applies worker completion
    events to sync_triggers. The backend is the only writer of that table; this is where
    worker-reported outcomes actually land."""
    client = get_pulsar_client()
    consumer = client.subscribe(GMAIL_SYNC_EVENTS_TOPIC, GMAIL_SYNC_EVENTS_SUBSCRIPTION)

    global _stop
    _stop = False

    try:
        while not _stop:
            msg = await asyncio.to_thread(_receive_one, consumer, 2000)
            if msg is None:
                continue

            try:
                event = GmailSyncEvent.model_validate_json(msg.data())
                async with AsyncSessionLocal() as db:
                    await sync_trigger_service.mark_completed(
                        db, uuid.UUID(event.trigger_id), event.status, event.error
                    )
                consumer.acknowledge(msg)
            except Exception:
                logger.exception("Failed to process gmail-sync-events message")
                consumer.negative_acknowledge(msg)
    finally:
        consumer.close()


def stop_consuming() -> None:
    global _stop
    _stop = True
