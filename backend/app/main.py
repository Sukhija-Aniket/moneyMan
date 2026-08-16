import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import accounts, auth, blacklist, categories, export, gmail, summary, transactions
from app.services import sync_events_consumer
from moneyman_shared.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(sync_events_consumer.consume_sync_events_forever())
    yield
    sync_events_consumer.stop_consuming()
    await consumer_task


app = FastAPI(title="Moneyman API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(gmail.router)
app.include_router(blacklist.router)
app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(export.router)
app.include_router(categories.router)
app.include_router(accounts.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
