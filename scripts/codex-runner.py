import argparse
import asyncio
import logging
import os
import time
from collections.abc import Mapping

import httpx
from aiwardrobe_core.codex_cli import CodexCliError, CodexCliRunner
from aiwardrobe_core.codex_relay import CodexRelayJob
from aiwardrobe_core.config import Settings
from aiwardrobe_core.llm_gateway import GarmentAnalysis, LookAnalysis
from pydantic import BaseModel

logger = logging.getLogger("aiwardrobe.codex_runner")

_SCHEMA_MODELS: Mapping[str, type[BaseModel] | None] = {
    "GarmentAnalysis": GarmentAnalysis,
    "LookAnalysis": LookAnalysis,
    "json_object": None,
}


def _runner_settings() -> Settings:
    return Settings.model_validate(
        {
            "codex_cli_command": os.environ.get("CODEX_CLI_COMMAND", "codex"),
            "codex_cli_model": os.environ.get("CODEX_CLI_MODEL", ""),
            "codex_cli_local_provider": os.environ.get("CODEX_CLI_LOCAL_PROVIDER", "none"),
            "codex_cli_timeout_seconds": int(os.environ.get("CODEX_CLI_TIMEOUT_SECONDS", "180")),
            "codex_cli_max_output_bytes": int(os.environ.get("CODEX_CLI_MAX_OUTPUT_BYTES", "1000000")),
            "codex_cli_ignore_user_config": os.environ.get("CODEX_CLI_IGNORE_USER_CONFIG", "true").lower() == "true",
            "codex_cli_allow_api_key_env": os.environ.get("CODEX_CLI_ALLOW_API_KEY_ENV", "false").lower() == "true",
            "max_upload_bytes": int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        }
    )


class LocalCodexService:
    """Long-poll the server and execute claimed jobs with the local Codex CLI."""

    def __init__(self, server_url: str, token: str, settings: Settings) -> None:
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.runner = CodexCliRunner(settings)
        self.claim_timeout = int(os.environ.get("CODEX_RUNNER_CLAIM_TIMEOUT_SECONDS", "15"))

    async def run(self, *, once: bool = False) -> None:
        if not await self.runner.probe():
            raise RuntimeError("Codex CLI is unavailable or failed its version probe.")
        timeout = httpx.Timeout(
            connect=10,
            read=self.claim_timeout + 15,
            write=30,
            pool=10,
        )
        headers = {"Authorization": f"Bearer {self.token}"}
        backoff_seconds = 1.0
        async with httpx.AsyncClient(base_url=self.server_url, headers=headers, timeout=timeout) as client:
            while True:
                try:
                    response = await client.post("/internal/codex-runner/claim")
                    if response.status_code == 204:
                        backoff_seconds = 1.0
                        if once:
                            return
                        continue
                    response.raise_for_status()
                    job = CodexRelayJob.model_validate(response.json())
                    await self._execute_job(client, job)
                    backoff_seconds = 1.0
                    if once:
                        return
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("Runner relay request failed", extra={"error_type": exc.__class__.__name__})
                    if once:
                        raise
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, 30.0)

    async def _execute_job(self, client: httpx.AsyncClient, job: CodexRelayJob) -> None:
        started = time.perf_counter()
        try:
            response_model = _SCHEMA_MODELS[job.response_schema]
            result = await self.runner.run_json(
                job.prompt,
                response_model=response_model,
                image_data_urls=job.image_data_urls,
            )
            response = await client.post(
                f"/internal/codex-runner/jobs/{job.job_id}/complete",
                json={"result": result},
            )
            response.raise_for_status()
            logger.info(
                "Runner job completed",
                extra={
                    "operation": job.operation,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
        except (CodexCliError, KeyError, ValueError) as exc:
            logger.warning(
                "Runner job failed",
                extra={"operation": job.operation, "error_type": exc.__class__.__name__},
            )
            response = await client.post(
                f"/internal/codex-runner/jobs/{job.job_id}/fail",
                json={"error_code": exc.__class__.__name__},
            )
            response.raise_for_status()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the trusted local Codex worker for AI Wardrobe.")
    parser.add_argument("--once", action="store_true", help="Process at most one claim response, then exit.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    server_url = os.environ.get("CODEX_RUNNER_SERVER_URL", "").strip()
    token = os.environ.get("CODEX_RUNNER_TOKEN", "").strip()
    if not server_url.startswith(("http://", "https://")):
        raise SystemExit("CODEX_RUNNER_SERVER_URL must be an HTTP(S) URL.")
    if len(token) < 32:
        raise SystemExit("CODEX_RUNNER_TOKEN must contain at least 32 characters.")
    logging.basicConfig(
        level=os.environ.get("CODEX_RUNNER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(LocalCodexService(server_url, token, _runner_settings()).run(once=args.once))


if __name__ == "__main__":
    main()
