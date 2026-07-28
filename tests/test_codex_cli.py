import asyncio
import json
from base64 import b64encode
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiwardrobe_core.codex_cli import CodexCliError, CodexCliRunner
from aiwardrobe_core.codex_relay import CodexRelay, CodexRunnerUnavailable
from aiwardrobe_core.config import Settings
from aiwardrobe_core.llm_gateway import LlmGateway
from pydantic import BaseModel


class SampleResponse(BaseModel):
    label: str
    score: float


class FakeCodexRunner(CodexCliRunner):
    def __init__(self, settings: Settings, response: dict[str, Any]) -> None:
        super().__init__(settings)
        self.response = response
        self.captured_args: list[str] = []
        self.captured_image = b""
        self.captured_schema: dict[str, Any] = {}

    def executable_path(self) -> str | None:
        return "codex-test"

    async def _execute(self, args: list[str], stdin_data: bytes) -> tuple[int, bytes, bytes]:
        self.captured_args = args
        assert b"Inspect the attached garment." in stdin_data
        output_path = Path(args[args.index("--output-last-message") + 1])
        image_path = Path(args[args.index("--image") + 1])
        schema_path = Path(args[args.index("--output-schema") + 1])
        self.captured_image = await asyncio.to_thread(image_path.read_bytes)
        schema_raw = await asyncio.to_thread(schema_path.read_text, encoding="utf-8")
        self.captured_schema = json.loads(schema_raw)
        await asyncio.to_thread(output_path.write_text, json.dumps(self.response), encoding="utf-8")
        return 0, b"", b""


def test_settings_expose_hybrid_capabilities_without_claiming_image_generation() -> None:
    settings = Settings(ai_execution_mode="hybrid", openrouter_api_key="", codex_runner_token="x" * 32)

    assert settings.ai_analysis_enabled is True
    assert settings.ai_analysis_provider == "hybrid:runner_first"
    assert settings.ai_analysis_model == "codex-cli-default"
    assert settings.image_generation_enabled is False
    assert settings.image_generation_provider == "unconfigured"


async def test_codex_runner_materializes_private_image_and_validates_response() -> None:
    runner = FakeCodexRunner(
        Settings(ai_execution_mode="cli"),
        {"label": "рубашка", "score": 0.92},
    )
    image = b"\x89PNG\r\n\x1a\nprivate-image"

    result = await runner.run_json(
        "Inspect the attached garment.",
        response_model=SampleResponse,
        image_data_urls=[f"data:image/png;base64,{b64encode(image).decode()}"],
    )

    assert result == {"label": "рубашка", "score": 0.92}
    assert runner.captured_image == image
    assert "--ephemeral" in runner.captured_args
    assert ["--sandbox", "read-only"] == runner.captured_args[
        runner.captured_args.index("--sandbox") : runner.captured_args.index("--sandbox") + 2
    ]
    assert "--output-schema" in runner.captured_args
    assert "--ignore-user-config" in runner.captured_args
    assert "--ignore-rules" in runner.captured_args
    assert runner.captured_schema["additionalProperties"] is False
    assert runner.captured_schema["required"] == ["label", "score"]


def test_codex_runner_does_not_forward_application_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-leak")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "must-not-leak")
    monkeypatch.setenv("CODEX_API_KEY", "explicit-only")

    default_environment = CodexCliRunner(Settings())._subprocess_environment()
    explicit_environment = CodexCliRunner(Settings(codex_cli_allow_api_key_env=True))._subprocess_environment()

    assert "OPENROUTER_API_KEY" not in default_environment
    assert "TELEGRAM_BOT_TOKEN" not in default_environment
    assert "CODEX_API_KEY" not in default_environment
    assert explicit_environment["CODEX_API_KEY"] == "explicit-only"


async def test_codex_runner_rejects_non_inline_or_invalid_images() -> None:
    runner = FakeCodexRunner(Settings(ai_execution_mode="cli"), {"label": "x", "score": 1})

    with pytest.raises(CodexCliError, match="inline JPEG"):
        await runner.run_json("inspect", image_data_urls=["https://private.example/image.jpg"])
    with pytest.raises(CodexCliError, match="valid base64"):
        await runner.run_json("inspect", image_data_urls=["data:image/png;base64,%%%"])


async def test_hybrid_gateway_falls_back_to_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_runner(self: CodexRelay, **_kwargs: Any) -> dict[str, Any]:
        raise CodexRunnerUnavailable("local runner unavailable")

    class FakeAsyncClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def post(self, *_args: Any, **_kwargs: Any) -> httpx.Response:
            request = httpx.Request("POST", "https://openrouter.test/chat/completions")
            return httpx.Response(
                200,
                request=request,
                json={"choices": [{"message": {"content": '{"reply":"fallback"}'}}]},
            )

    monkeypatch.setattr(CodexRelay, "submit_and_wait", fail_runner)
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    gateway = LlmGateway(
        Settings(
            ai_execution_mode="hybrid",
            ai_hybrid_preference="runner_first",
            openrouter_api_key="sk-test",
            codex_runner_token="x" * 32,
        )
    )

    assert await gateway.generate_text_json("hello", "Chat") == {"reply": "fallback"}
    assert gateway.last_provider == "openrouter"


async def test_runner_gateway_does_not_require_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    async def complete_runner(self: CodexRelay, **_kwargs: Any) -> dict[str, Any]:
        return {"reply": "local"}

    monkeypatch.setattr(CodexRelay, "submit_and_wait", complete_runner)
    gateway = LlmGateway(Settings(ai_execution_mode="runner", openrouter_api_key="", codex_runner_token="x" * 32))

    assert await gateway.generate_text_json("hello", "Chat") == {"reply": "local"}
    assert gateway.last_provider == "codex_runner"
    assert gateway.last_model == "codex-cli-default"
