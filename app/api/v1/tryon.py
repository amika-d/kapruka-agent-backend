import httpx
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("tryon")

FAL_QUEUE_BASE = "https://queue.fal.run/fal-ai/image-apps-v2/virtual-try-on"
FAL_STATUS_BASE = "https://queue.fal.run/fal-ai/image-apps-v2/virtual-try-on/requests"
POLL_INTERVAL = 3      # seconds between status checks
MAX_WAIT = 120         # give up after 2 minutes


class TryOnRequest(BaseModel):
    user_image_base64: str
    garment_image_url: str
    garment_description: str = ""


class TryOnResult(BaseModel):
    result_image_url: str
    processing_time_ms: int
    request_id: str | None = None


@router.post("/tryon")
async def try_on(payload: TryOnRequest) -> TryOnResult:
    fal_api_key = settings.effective_fal_key
    if not fal_api_key:
        logger.error("tryon: no FAL key configured")
        raise HTTPException(status_code=500, detail="Try-on not configured")

    headers = {
        "Authorization": f"Key {fal_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "person_image_url": f"data:image/jpeg;base64,{payload.user_image_base64}",
        "clothing_image_url": payload.garment_image_url,
    }

    start = time.time()

    async with httpx.AsyncClient(timeout=30.0) as client:

        # 1. Submit to queue
        logger.info("tryon: submitting to fal queue — garment=%s b64_len=%d",
                    payload.garment_image_url, len(payload.user_image_base64))
        try:
            submit_res = await client.post(FAL_QUEUE_BASE, headers=headers, json=body)
        except httpx.RequestError as e:
            logger.error("tryon: submit failed: %s", e, exc_info=True)
            raise HTTPException(status_code=502, detail=f"fal unreachable: {e}")

        if submit_res.status_code != 200:
            logger.error("tryon: submit non-200: status=%d body=%s",
                         submit_res.status_code, submit_res.text[:2000])
            raise HTTPException(status_code=502, detail=f"fal submit failed: {submit_res.text}")

        request_id = submit_res.json().get("request_id")
        if not request_id:
            logger.error("tryon: no request_id in submit response: %s", submit_res.json())
            raise HTTPException(status_code=502, detail="fal returned no request_id")

        logger.info("tryon: queued — request_id=%s", request_id)

        # 2. Poll for completion
        status_url = f"{FAL_STATUS_BASE}/{request_id}/status"
        result_url_endpoint = f"{FAL_STATUS_BASE}/{request_id}"
        elapsed = 0

        while elapsed < MAX_WAIT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            try:
                status_res = await client.get(status_url, headers=headers)
            except httpx.RequestError as e:
                logger.warning("tryon: poll error (will retry): %s", e)
                continue

            if status_res.status_code != 200:
                logger.warning("tryon: poll non-200: %d — retrying", status_res.status_code)
                continue

            status_data = status_res.json()
            status = status_data.get("status")
            logger.info("tryon: poll status=%s elapsed=%ds request_id=%s", status, elapsed, request_id)

            if status == "COMPLETED":
                break
            elif status == "FAILED":
                logger.error("tryon: fal job failed: %s", status_data)
                raise HTTPException(status_code=502, detail="fal try-on job failed")
            # IN_QUEUE or IN_PROGRESS — keep polling

        else:
            logger.error("tryon: timed out after %ds — request_id=%s", MAX_WAIT, request_id)
            raise HTTPException(status_code=504, detail=f"Try-on timed out after {MAX_WAIT}s")

        # 3. Fetch result
        try:
            result_res = await client.get(result_url_endpoint, headers=headers)
        except httpx.RequestError as e:
            logger.error("tryon: result fetch failed: %s", e, exc_info=True)
            raise HTTPException(status_code=502, detail=f"fal result fetch failed: {e}")

        if result_res.status_code != 200:
            logger.error("tryon: result non-200: status=%d body=%s",
                         result_res.status_code, result_res.text[:2000])
            raise HTTPException(status_code=502, detail="fal result fetch failed")

        try:
            data = result_res.json()
        except ValueError as e:
            logger.error("tryon: result not valid JSON: %s body=%s", e, result_res.text[:2000])
            raise HTTPException(status_code=502, detail="fal result not valid JSON")

    images = data.get("images") or []
    result_image_url = images[0].get("url") if images else None

    if not result_image_url:
        logger.error("tryon: missing images[0].url — keys=%s raw=%s", list(data.keys()), data)
        raise HTTPException(status_code=502, detail="No result image returned")

    total_ms = int((time.time() - start) * 1000)
    logger.info("tryon: success — elapsed_ms=%d request_id=%s url=%s",
                total_ms, request_id, result_image_url)

    return TryOnResult(
        result_image_url=result_image_url,
        processing_time_ms=total_ms,
        request_id=request_id,
    )