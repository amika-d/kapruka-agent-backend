from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.v1 import chat, health, checkout, tryon, sessions

from app.core.config import settings
from app.mcp.client import close_client
from app.core.category_cache import load_categories_from_file
from app.core.database import get_session_store



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise category cache
    load_categories_from_file()
    get_session_store().load_from_disk()
    logger.info("Kiyanna is awake 🛒")
    yield
    get_session_store().save_to_disk()
    await close_client()
    logger.info("Kiyanna goes to sleep 💤")

app = FastAPI(title="Kiyanna API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        settings.frontend_url.rstrip("/"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex="https://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(checkout.router, prefix="/api/v1", tags=["checkout"])
app.include_router(tryon.router, prefix="/api/v1", tags=["tryon"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])


@app.get("/")
async def root():
    return {
        "name": "Kiyanna API",
        "version": "1.0.0",
        "status": "online"
    }
