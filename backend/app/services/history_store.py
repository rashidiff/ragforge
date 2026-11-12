"""Durable single-process canonical JSONL archive; never normalize message content."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

_LOCKS: dict[str, RLock] = {}
_GUARD = RLock()


class HistoryCorruptionError(RuntimeError):
    pass


class HistoryStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _GUARD:
            self.lock = _LOCKS.setdefault(str(self.path), RLock())
        self.recover()

    def recover(self):
        with self.lock:
            if not self.path.exists():
                return
            data = self.path.read_bytes()
            offset = 0
            for line in data.splitlines(keepends=True):
                if not line.endswith(b"\n"):
                    quarantine = self.path.with_name(self.path.name + ".partial-" + str(uuid4()))
                    with quarantine.open("xb") as out:
                        out.write(line)
                        out.flush()
                        os.fsync(out.fileno())
                    with self.path.open("r+b") as out:
                        out.truncate(offset)
                        out.flush()
                        os.fsync(out.fileno())
                    return
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise TypeError("record is not an object")
                except (ValueError, TypeError, UnicodeError) as exc:
                    raise HistoryCorruptionError(
                        "Archive contains corrupt complete records; restore a backup."
                    ) from exc
                offset += len(line)

    def records(self, chat_id=None):
        with self.lock:
            if not self.path.exists():
                return []
            records = [
                json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()
            ]
            return [r for r in records if chat_id is None or r.get("chat_id") == chat_id]

    def append_record(self, record):
        with self.lock, self.path.open("ab") as out:
            out.write(
                (json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            )
            out.flush()
            os.fsync(out.fileno())
        return record

    def append_message(
        self, chat_id, request_id, role, content, *, completed=True, message_id=None, metadata=None
    ):
        if role not in {"user", "assistant"} or not isinstance(content, str):
            raise ValueError("Invalid message")
        with self.lock:
            message_id = message_id or str(uuid4())
            existing = self.records()
            prior = next((r for r in existing if r.get("message_id") == message_id), None)
            if prior:
                if (
                    prior.get("chat_id"),
                    prior.get("role"),
                    prior.get("content"),
                    prior.get("completed"),
                ) != (chat_id, role, content, completed):
                    raise ValueError("Message ID already belongs to different content")
                return prior
            return self.append_record(
                {
                    "event_id": str(uuid4()),
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "request_id": request_id,
                    "role": role,
                    "content": content,
                    "completed": completed,
                    "created_at": datetime.now(UTC).isoformat(),
                    "metadata": {**(metadata or {}), "sequence": len(existing) + 1},
                }
            )
