import pulsar

from moneyman_shared.config import get_settings

_client: pulsar.Client | None = None


def get_pulsar_client() -> pulsar.Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = pulsar.Client(settings.PULSAR_SERVICE_URL)
    return _client


def close_pulsar_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
