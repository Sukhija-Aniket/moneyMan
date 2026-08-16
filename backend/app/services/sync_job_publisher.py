from moneyman_shared.messaging.client import get_pulsar_client
from moneyman_shared.messaging.schemas import GmailSyncJob
from moneyman_shared.messaging.topics import GMAIL_SYNC_JOBS_TOPIC

_producer = None


def _get_producer():
    global _producer
    if _producer is None:
        _producer = get_pulsar_client().create_producer(GMAIL_SYNC_JOBS_TOPIC)
    return _producer


def publish_sync_job(job: GmailSyncJob) -> None:
    _get_producer().send(job.model_dump_json().encode("utf-8"))
