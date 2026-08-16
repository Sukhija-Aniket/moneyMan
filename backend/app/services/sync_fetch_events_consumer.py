import asyncio
import logging
import uuid

from moneyman_shared.db.session import AsyncSessionLocal
from moneyman_shared.messaging.client import get_pulsar_client
from moneyman_shared.messaging.schemas import GmailSyncFetchEvent
from moneyman_shared.messaging.topics import (
    GMAIL_SYNC_FETCH_EVENTS_SUBSCRIPTION,
    GMAIL_SYNC_FETCH_EVENTS_TOPIC,
)

from app.services import sync_coverage_service, sync_request_service

logger = logging.getLogger(__name__)

_stop = False


def _receive_one(consumer, timeout_millis: int):
    """Pulsar's Python client is synchronous — run receive() in a thread so it doesn't
    block the asyncio event loop the rest of the backend runs on."""
    try:
        return consumer.receive(timeout_millis=timeout_millis)
    except Exception:
        return None


async def _apply_event(event: GmailSyncFetchEvent) -> None:
    async with AsyncSessionLocal() as db:
        segment_id = uuid.UUID(event.segment_id)
        segment = await sync_request_service.mark_segment_terminal(db, segment_id, event.status, event.error)
        if segment is None:
            await db.commit()
            return

        if event.status == "success" and segment.date_from is not None and segment.date_to is not None:
            await sync_coverage_service.merge_insert_synced_range(
                db, segment.user_id, segment.date_from, segment.date_to
            )

        await db.commit()
        await sync_request_service.maybe_finalize_request(db, segment.sync_request_id)


async def consume_sync_fetch_events_forever() -> None:
    """Background task (started at app startup, see main.py) that applies the worker's
    per-segment fetch-stage completion events to sync_segments/synced_ranges/sync_requests.
    The backend is the only writer of those tables; this is where worker-reported outcomes
    actually land."""
    client = get_pulsar_client()
    consumer = client.subscribe(GMAIL_SYNC_FETCH_EVENTS_TOPIC, GMAIL_SYNC_FETCH_EVENTS_SUBSCRIPTION)

    global _stop
    _stop = False

    try:
        while not _stop:
            msg = await asyncio.to_thread(_receive_one, consumer, 2000)
            if msg is None:
                continue

            try:
                event = GmailSyncFetchEvent.model_validate_json(msg.data())
                await _apply_event(event)
                consumer.acknowledge(msg)
            except Exception:
                logger.exception("Failed to process gmail-sync-fetch-events message")
                consumer.negative_acknowledge(msg)
    finally:
        consumer.close()


def stop_consuming() -> None:
    global _stop
    _stop = True
