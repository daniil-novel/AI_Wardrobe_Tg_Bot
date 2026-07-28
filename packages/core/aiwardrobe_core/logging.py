import logging
import re
from collections.abc import Mapping, MutableMapping
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

SENSITIVE_KEY_RE = re.compile(r"(authorization|token|secret|key|password|init_data|signed_url)", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]+)", re.IGNORECASE)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_VALUE_RE.sub("[REDACTED]", value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        redacted[key] = "[REDACTED]" if SENSITIVE_KEY_RE.search(str(key)) else redact_value(value)
    return redacted


def hash_identifier(value: str) -> str:
    return sha256(value.encode()).hexdigest()[:16]


def configure_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s %(message)s"))
            handlers.append(file_handler)
        except OSError:
            # A read-only or missing log volume must never take the service down.
            logging.getLogger(__name__).warning("Log file %s is not writable; file logging disabled", log_file)
    logging.basicConfig(level=log_level, format="%(message)s", handlers=handlers, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_log_level,
            redact_event,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def add_log_level(_: Any, method_name: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
    event_dict["level"] = method_name
    return event_dict


def redact_event(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
    return redact_mapping(event_dict)
