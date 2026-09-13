"""
Logging configuration with ContextVar correlation tracking and SIEM JSON formatting.
"""
import contextvars
import json
import logging
import sys
from typing import Optional

from backend.app.config import settings

# Global async-safe context variable for correlation ID
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str:
    """Retrieve the active correlation ID or '-' if outside an active request context."""
    return correlation_id_ctx.get() or "-"


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects correlation_id into log records for any formatter."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        return True


class StructuredJsonFormatter(logging.Formatter):
    """Structured JSON formatter for enterprise SIEM ingestion."""
    def format(self, record: logging.LogRecord) -> str:
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": cid,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    root_logger = logging.getLogger()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationIdFilter())

    use_json = (
        getattr(settings, "LOG_FORMAT", "").lower() == "json"
        or getattr(settings, "APP_ENV", "") == "production"
    )

    if use_json:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        text_format = "[%(asctime)s] [%(levelname)s] [%(name)s] [%(correlation_id)s] %(message)s"
        handler.setFormatter(logging.Formatter(text_format))

    root_logger.handlers = [handler]

    # Configure uvicorn loggers to inherit the same formatter
    for uvicorn_log in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_log)
        u_logger.handlers = [handler]
        u_logger.propagate = False


logger = logging.getLogger("crypto_tracer")
