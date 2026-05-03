from uuid import uuid4

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.schemas import AiTaskRequest, AiTaskStatus
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-image", response_model=AiTaskStatus)
async def analyze_image(payload: AiTaskRequest) -> AiTaskStatus:
    if not get_settings().openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENROUTER_API_KEY is required; mock AI mode is intentionally disabled.",
        )
    return AiTaskStatus(task_id=str(uuid4()), status="queued")


@router.get("/tasks/{task_id}", response_model=AiTaskStatus)
async def get_task(task_id: str) -> AiTaskStatus:
    return AiTaskStatus(task_id=task_id, status="processing")


@router.post("/tasks/{task_id}/retry", response_model=AiTaskStatus)
async def retry_task(task_id: str) -> AiTaskStatus:
    return AiTaskStatus(task_id=task_id, status="queued")


@router.get("/usage")
async def usage() -> dict[str, int | float]:
    return {"requests_today": 0, "cost_usd_today": 0.0}
