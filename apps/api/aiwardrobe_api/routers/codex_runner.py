import hmac
from typing import Annotated, Any
from uuid import UUID

from aiwardrobe_core.codex_relay import CodexRelay, CodexRelayJob, relay_payload_size
from aiwardrobe_core.config import Settings, get_settings
from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/internal/codex-runner", tags=["internal"], include_in_schema=False)


class RunnerCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]


class RunnerFailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(min_length=1, max_length=128)


def require_runner_token(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings | None = None,
) -> Settings:
    resolved_settings = settings or get_settings()
    expected = resolved_settings.codex_runner_token
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if len(expected) < 32 or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid runner credentials.",
        )
    return resolved_settings


@router.post("/heartbeat")
async def heartbeat(authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
    settings = require_runner_token(authorization)
    await CodexRelay(settings).heartbeat()
    return {"status": "connected"}


@router.post("/claim", response_model=CodexRelayJob, responses={204: {"description": "No pending job"}})
async def claim(authorization: Annotated[str | None, Header()] = None) -> CodexRelayJob | Response:
    settings = require_runner_token(authorization)
    job = await CodexRelay(settings).claim()
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job


@router.post("/jobs/{job_id}/complete")
async def complete(
    job_id: UUID,
    payload: RunnerCompleteRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    settings = require_runner_token(authorization)
    if relay_payload_size(payload.result) > settings.codex_cli_max_output_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Runner response is too large.")
    accepted = await CodexRelay(settings).complete(job_id, payload.result)
    if not accepted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Runner job is no longer active.")
    return {"status": "accepted"}


@router.post("/jobs/{job_id}/fail")
async def fail(
    job_id: UUID,
    payload: RunnerFailRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    settings = require_runner_token(authorization)
    accepted = await CodexRelay(settings).fail(job_id, payload.error_code)
    if not accepted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Runner job is no longer active.")
    return {"status": "accepted"}
