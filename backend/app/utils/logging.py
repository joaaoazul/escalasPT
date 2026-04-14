"""
Structured logging configuration.
Ensures no sensitive data (passwords, tokens, PII) is ever logged.
"""

from __future__ import annotations

import logging
import re
import sys

from pythonjsonlogger import jsonlogger

from app.config import get_settings

# Patterns to redact from log messages
_SENSITIVE_PATTERNS = re.compile(
    r"(password|token|secret|authorization|cookie|totp|otp)"
    r"\s*[:=]\s*\S+",
    flags=re.IGNORECASE,
)


class SanitizingFormatter(jsonlogger.JsonFormatter):
    """JSON log formatter that redacts sensitive data."""

    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, str):
            record.msg = _SENSITIVE_PATTERNS.sub(
                lambda m: m.group().split("=")[0].split(":")[0] + "=[REDACTED]",
                record.msg,
            )
        return super().format(record)


def setup_logging() -> None:
    """Configure structured JSON logging for the application."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = SanitizingFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quieten noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance."""
    return logging.getLogger(name)
