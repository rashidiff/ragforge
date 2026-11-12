"""Bounded in-flight generation leases, isolated by chat."""

from dataclasses import dataclass
from contextlib import contextmanager
from threading import RLock
from uuid import uuid4

from app.llm.base import Cancellation


class GenerationConflictError(RuntimeError):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GenerationLease:
    chat_id: str
    lease_id: str
    cancellation: Cancellation


class GenerationRegistry:
    def __init__(self, maximum: int):
        self.maximum = maximum
        self._active: dict[str, GenerationLease] = {}
        self._lock = RLock()

    def acquire(self, chat_id: str) -> GenerationLease:
        with self._lock:
            if chat_id in self._active:
                raise GenerationConflictError("A response is already running for this chat")
            if len(self._active) >= self.maximum:
                raise GenerationConflictError("The local generation limit is busy", status_code=429)
            lease = GenerationLease(chat_id, str(uuid4()), Cancellation())
            self._active[chat_id] = lease
            return lease

    def release(self, lease: GenerationLease) -> None:
        with self._lock:
            current = self._active.get(lease.chat_id)
            if current is not None and current.lease_id == lease.lease_id:
                self._active.pop(lease.chat_id, None)

    @contextmanager
    def configuration_change(self):
        """Keep provider/model changes atomic with generation lease acquisition."""
        with self._lock:
            if self._active:
                raise GenerationConflictError("Wait for the current response before changing model settings")
            yield

    def cancel(self, chat_id: str) -> bool:
        with self._lock:
            lease = self._active.get(chat_id)
            if lease is None:
                return False
            lease.cancellation.cancel()
            return True
