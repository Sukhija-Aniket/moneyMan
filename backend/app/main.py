from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import accounts, auth, categories, export, gmail, summary, transactions
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Moneyman API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(gmail.router)
app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(export.router)
app.include_router(categories.router)
app.include_router(accounts.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
