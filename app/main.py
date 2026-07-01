from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.v1 import chat, health, checkout

from app.core.config import settings
from app.mcp.client import close_client
from app.core.category_cache import load_categories_from_file



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise category cache
    load_categories_from_file()
    logger.info("Kiyanna is awake 🛒")
    yield
    await close_client()
    logger.info("Kiyanna goes to sleep 💤")

app = FastAPI(title="Kiyanna API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,          # production: https://kapruka.bitzandbeyond.com
        "http://localhost:3000",         # local dev
        "http://127.0.0.1:3000",        # local dev (alternate)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(checkout.router, prefix="/api/v1", tags=["checkout"])


@app.get("/")
async def root():
    return {
        "name": "Kiyanna API",
        "version": "1.0.0",
        "status": "online"
    }
