from aiwardrobe_core.config import get_settings
from aiwardrobe_core.schemas import HealthResponse
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        missing_runtime_secrets=settings.missing_runtime_secrets,
    )
