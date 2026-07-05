import asyncio
import logging
import time

import fal_client
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("tryon")


class TryOnRequest(BaseModel):
    user_image_base64: str
    garment_image_url: str
    garment_description: str = ""


class TryOnResult(BaseModel):
    result_image_url: str
    processing_time_ms: int
    request_id: str | None = None


def _on_queue_update(update):
    # fal_client calls this synchronously from the worker thread while
    # subscribe() is polling — just forward the logs, don't do anything
    # blocking or async here.
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            logger.info("tryon: fal log — %s", log.get("message"))


def _run_tryon_sync(person_image_url: str, clothing_image_url: str) -> dict:
    """Blocking call — fal_client.subscribe() submits, polls, and waits
    for completion internally. Must be run off the event loop via
    asyncio.to_thread, since fal_client has no native asyncio support."""
    return fal_client.subscribe(
        settings.tryon_app_id,
        arguments={
            "human_image_url": person_image_url,
            "garment_image_url": clothing_image_url,
        },
        with_logs=True,
        on_queue_update=_on_queue_update,
    )


@router.post("/tryon")
async def try_on(payload: TryOnRequest) -> TryOnResult:
    if not settings.effective_fal_key:
        logger.error("tryon: no FAL key configured")
        raise HTTPException(status_code=500, detail="Try-on not configured")

    person_image_url = f"data:image/jpeg;base64,{payload.user_image_base64}"

    logger.info(
        "tryon: submitting via fal_client — app=%s garment=%s b64_len=%d",
        settings.tryon_app_id, payload.garment_image_url, len(payload.user_image_base64),
    )

    start = time.time()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_tryon_sync, person_image_url, payload.garment_image_url),
            timeout=settings.tryon_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("tryon: timed out after %ds", settings.tryon_timeout)
        raise HTTPException(status_code=504, detail=f"Try-on timed out after {settings.tryon_timeout}s")
    except fal_client.FalClientError as e:
        # Covers submit failures and job-level FAILED status raised by fal_client.
        logger.error("tryon: fal_client error: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"fal try-on failed: {e}")

    # NOTE — schema depends on which fal app you're calling:
    #   fal-ai/kling/v1-5/kolors-virtual-try-on  -> {"image": {"url": ...}}          (singular)
    #   fal-ai/image-apps-v2/virtual-try-on      -> {"images": [{"url": ...}, ...]}  (array)
    # This is written for the Kling schema shown in your docs. If you're
    # still pointed at image-apps-v2, swap the two lines below.
    image = result.get("image")
    result_image_url = image.get("url") if image else None

    if not result_image_url:
        logger.error("tryon: missing image.url — keys=%s raw=%s", list(result.keys()), result)
        raise HTTPException(status_code=502, detail="No result image returned")

    total_ms = int((time.time() - start) * 1000)
    request_id = result.get("request_id")
    logger.info(
        "tryon: success — elapsed_ms=%d request_id=%s url=%s",
        total_ms, request_id, result_image_url,
    )

    return TryOnResult(
        result_image_url=result_image_url,
        processing_time_ms=total_ms,
        request_id=request_id,
    )