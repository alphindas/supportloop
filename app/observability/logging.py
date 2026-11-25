"""Structured JSON logs: one JSON object per line."""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Format records as JSON. Extra data goes in `extra={"fields": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        """Turn one record into one line of JSON."""
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Send the application's logs to stdout as JSON."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("supportloop")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
