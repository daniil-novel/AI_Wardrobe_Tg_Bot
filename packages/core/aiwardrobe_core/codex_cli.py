import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from base64 import b64decode
from binascii import Error as Base64Error
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from aiwardrobe_core.config import Settings

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_SAFE_ENVIRONMENT_KEYS = {
    "APPDATA",
    "CODEX_HOME",
    "COMSPEC",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}


class CodexCliError(RuntimeError):
    """Raised when the isolated Codex CLI inference process fails."""


class CodexCliRunner:
    """Run structured Codex inference in an isolated, read-only temporary workspace."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def executable_path(self) -> str | None:
        """Resolve the configured executable without invoking a shell."""
        return shutil.which(self.settings.codex_cli_command)

    async def probe(self) -> bool:
        """Return whether the configured Codex executable starts successfully."""
        executable = self.executable_path()
        if executable is None:
            return False
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "--version",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            return False
        try:
            await asyncio.wait_for(process.communicate(), timeout=10)
        except TimeoutError:
            process.kill()
            await process.communicate()
            return False
        return process.returncode == 0

    async def run_json(
        self,
        prompt: str,
        *,
        response_model: type[BaseModel] | None = None,
        image_data_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run Codex and return a validated JSON object.

        Args:
            prompt: Trusted application instruction. User image contents remain untrusted data.
            response_model: Optional Pydantic response contract.
            image_data_urls: Inline base64 images to materialize only for the subprocess lifetime.

        Returns:
            Parsed JSON object from the final Codex message.

        Raises:
            CodexCliError: If the executable, input, subprocess, or response is invalid.
        """
        executable = self.executable_path()
        if executable is None:
            raise CodexCliError(f"Codex CLI executable was not found: {self.settings.codex_cli_command!r}.")

        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="aiwardrobe-codex-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            image_paths = await self._write_images(temp_dir, image_data_urls or [])
            response_path = temp_dir / "response.json"
            args = self._build_args(
                executable=executable,
                temp_dir=temp_dir,
                response_path=response_path,
                image_paths=image_paths,
                response_model=response_model,
            )
            return_code, _, _stderr = await self._execute(args, prompt.encode("utf-8"))
            if return_code != 0:
                raise CodexCliError(
                    f"Codex CLI exited with status {return_code}; diagnostic output was suppressed for privacy."
                )
            try:
                raw_output = await asyncio.to_thread(response_path.read_text, encoding="utf-8")
            except OSError as exc:
                raise CodexCliError("Codex CLI did not write its final response.") from exc
            if len(raw_output.encode("utf-8")) > self.settings.codex_cli_max_output_bytes:
                raise CodexCliError("Codex CLI response exceeded the configured size limit.")
            try:
                parsed: Any = json.loads(_extract_json_object(raw_output))
            except json.JSONDecodeError as exc:
                raise CodexCliError("Codex CLI response was not valid JSON.") from exc
            if not isinstance(parsed, dict):
                raise CodexCliError("Codex CLI response was not a JSON object.")
            result: dict[str, Any] = {str(key): value for key, value in parsed.items()}
            if response_model is not None:
                result = response_model.model_validate(result).model_dump(mode="json")
            logger.info(
                "Codex CLI inference completed",
                extra={
                    "provider": "codex_cli",
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "image_count": len(image_paths),
                },
            )
            return result

    def _build_args(
        self,
        *,
        executable: str,
        temp_dir: Path,
        response_path: Path,
        image_paths: list[Path],
        response_model: type[BaseModel] | None,
    ) -> list[str]:
        args = [
            executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--cd",
            str(temp_dir),
            "--output-last-message",
            str(response_path),
        ]
        if self.settings.codex_cli_ignore_user_config:
            args.extend(["--ignore-user-config", "--ignore-rules"])
        if self.settings.codex_cli_model:
            args.extend(["--model", self.settings.codex_cli_model])
        if self.settings.codex_cli_local_provider != "none":
            args.extend(["--oss", "--local-provider", self.settings.codex_cli_local_provider])
        if response_model is not None:
            schema_path = temp_dir / "schema.json"
            schema_path.write_text(
                json.dumps(_strict_json_schema(response_model.model_json_schema()), ensure_ascii=False),
                encoding="utf-8",
            )
            args.extend(["--output-schema", str(schema_path)])
        # `--image <FILE>...` is variadic, so the stdin marker must precede it.
        # Stdin also keeps private prompts out of process listings and preserves UTF-8 on Windows.
        args.append("-")
        for image_path in image_paths:
            args.extend(["--image", str(image_path)])
        return args

    async def _execute(self, args: list[str], stdin_data: bytes) -> tuple[int, bytes, bytes]:
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._subprocess_environment(),
            )
        except OSError as exc:
            raise CodexCliError("Codex CLI process could not be started.") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin_data),
                timeout=self.settings.codex_cli_timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise CodexCliError(f"Codex CLI exceeded the {self.settings.codex_cli_timeout_seconds}s timeout.") from exc
        return process.returncode or 0, stdout, stderr

    async def _write_images(self, temp_dir: Path, data_urls: list[str]) -> list[Path]:
        paths: list[Path] = []
        for index, data_url in enumerate(data_urls):
            content_type, content = self._decode_image_data_url(data_url)
            image_path = temp_dir / f"input-{index}{_IMAGE_EXTENSIONS[content_type]}"
            await asyncio.to_thread(image_path.write_bytes, content)
            paths.append(image_path)
        return paths

    def _decode_image_data_url(self, data_url: str) -> tuple[str, bytes]:
        header, separator, encoded = data_url.partition(",")
        if separator != "," or not header.startswith("data:image/") or not header.endswith(";base64"):
            raise CodexCliError("Codex CLI accepts only inline JPEG, PNG, or WebP image data.")
        content_type = header.removeprefix("data:").removesuffix(";base64").lower()
        if content_type not in _IMAGE_EXTENSIONS:
            raise CodexCliError(f"Unsupported Codex CLI image type: {content_type}.")
        try:
            content = b64decode(encoded, validate=True)
        except (Base64Error, ValueError) as exc:
            raise CodexCliError("Codex CLI image data is not valid base64.") from exc
        if not content or len(content) > self.settings.max_upload_bytes:
            raise CodexCliError("Codex CLI image is empty or exceeds the upload limit.")
        return content_type, content

    def _subprocess_environment(self) -> dict[str, str]:
        environment = {key: value for key, value in os.environ.items() if key.upper() in _SAFE_ENVIRONMENT_KEYS}
        if self.settings.codex_cli_allow_api_key_env:
            codex_api_key = os.environ.get("CODEX_API_KEY")
            if codex_api_key:
                environment["CODEX_API_KEY"] = codex_api_key
        environment["NO_COLOR"] = "1"
        return environment


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return content
    return content[start : end + 1]


def _strict_json_schema(value: Any) -> Any:
    """Convert Pydantic output into the strict object schema required by Codex."""
    if isinstance(value, list):
        return [_strict_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {key: _strict_json_schema(item) for key, item in value.items()}
    properties = normalized.get("properties")
    if normalized.get("type") == "object" and isinstance(properties, dict):
        normalized["additionalProperties"] = False
        normalized["required"] = list(properties)
    return normalized
