import asyncio
import json
import os

from aiwardrobe_core.codex_relay import CodexRelay
from aiwardrobe_core.config import Settings


async def main() -> None:
    settings = Settings.model_validate(
        {
            "ai_execution_mode": "runner",
            "codex_runner_token": os.environ["CODEX_RUNNER_TOKEN"],
            "redis_url": os.environ.get("REDIS_URL", "redis://127.0.0.1:6389/0"),
            "codex_runner_wait_timeout_seconds": 120,
        }
    )
    result = await CodexRelay(settings).submit_and_wait(
        operation="generate_text_json",
        prompt=(
            'Return only a JSON object with exactly these values: {"status":"ok","transport":"redis_https_codex_cli"}.'
        ),
        response_schema="json_object",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
