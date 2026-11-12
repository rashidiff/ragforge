"""Atomic local snapshots with explicit corruption and recovery semantics."""
from copy import deepcopy
import json
import os
from pathlib import Path
from threading import RLock
from typing import Callable, TypeVar
from uuid import uuid4

T = TypeVar("T")
_LOCKS: dict[Path, RLock] = {}
_GUARD = RLock()


class StateCorruptionError(RuntimeError):
    pass


def durable_replace(path: Path, content: bytes) -> None:
    """Publish complete bytes from a unique file on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class JsonState:
    def __init__(self, path: Path, initial: dict):
        self.path = path.resolve()
        self.initial = deepcopy(initial)
        with _GUARD:
            self.lock = _LOCKS.setdefault(self.path, RLock())

    def read(self) -> dict:
        with self.lock:
            if not self.path.exists():
                return deepcopy(self.initial)
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(value, dict) or value.get("schema_version") != 1:
                    raise ValueError("Unsupported snapshot schema")
                return value
            except (ValueError, UnicodeError) as exc:
                raise StateCorruptionError(
                    "State snapshot is corrupt or incompatible. Restore a compatible backup."
                ) from exc

    def update(self, mutate: Callable[[dict], T]) -> T:
        with self.lock:
            state = self.read()
            result = mutate(state)
            content = json.dumps(state, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if self.path.exists():
                durable_replace(self.path.with_suffix(self.path.suffix + ".bak"),
                                self.path.read_bytes())
            durable_replace(self.path, content)
            return result
