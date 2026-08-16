import asyncio
import logging

from worker.extraction_stage import run_extraction_stage_forever
from worker.fetch_stage import FetchStage, run_fetch_stage_forever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Single worker process running both pipeline stages from docs/design.md as concurrent
# asyncio tasks — the two stages are separated by Pulsar topics (the real seam), not by OS
# process, so one process is enough for now. Either stage can be split into its own
# deployable later without changing the message contracts.


async def run_forever() -> None:
    fetch_stage = FetchStage()
    await asyncio.gather(
        run_fetch_stage_forever(fetch_stage),
        run_extraction_stage_forever(),
    )


if __name__ == "__main__":
    asyncio.run(run_forever())
