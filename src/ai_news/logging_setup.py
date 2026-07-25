import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "AUTHORIZATION")


def redact_sensitive(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if any(marker in key.upper() for marker in SENSITIVE_MARKERS):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], dict):
            event_dict[key] = redact_sensitive(None, "", event_dict[key])
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redact_sensitive,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
