"""Redacted operational events kept separate from verbatim history."""

import re
from datetime import UTC, datetime

from .history_store import HistoryStore

_PATTERN = re.compile(
    r"(?i)(?:bearer\s+[^\s,;]+|(?:sk-|AIza)[A-Za-z0-9_-]{12,}|(?:api[_ -]?key|authorization|access[_ -]?token)\s*[:=]\s*[^\s,;]+)"
)
_SENSITIVE = {"api_key", "authorization", "headers", "access_token", "bearer_token", "prompt"}


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in _SENSITIVE else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return _PATTERN.sub("[REDACTED]", value) if isinstance(value, str) else value


class ActivityLogger:
    def __init__(self, path):
        self.store = HistoryStore(path)

    def emit(self, event_type, severity="INFO", **fields):
        # Do not accept SDK response/request objects: callers supply explicit safe fields.
        record = redact(fields)
        record.update(
            timestamp=datetime.now(UTC).isoformat(), severity=severity, event_type=event_type
        )
        return self.store.append_record(record)
