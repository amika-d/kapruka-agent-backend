from fastapi import APIRouter, status
import time

router = APIRouter()

# Track start time for uptime calculation
START_TIME = time.time()

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Liveness and readiness probe endpoint.
    """
    return {
        "status": "healthy",
        "uptime_seconds": int(time.time() - START_TIME),
        "version": "1.0.0"
    }