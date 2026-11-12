"""Chat metadata and explicit, isolated deletion of canonical message history."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from .history_store import HistoryStore
from .state_store import JsonState, StateCorruptionError, durable_replace


def now() -> str:
    return datetime.now(UTC).isoformat()


class ChatNotFoundError(LookupError):
    pass


class ChatStore:
    def __init__(self, data_dir: Path, history: HistoryStore):
        self.history = history
        self.state = JsonState(data_dir / "state/chats.json", {"schema_version": 1, "chats": {}})
        self.compactions = JsonState(
            data_dir / "state/compactions.json", {"schema_version": 1, "chats": {}}
        )

    def _chats(self, state: dict) -> dict:
        chats = state.get("chats")
        if not isinstance(chats, dict):
            raise StateCorruptionError("Chat metadata is corrupt; restore a backup.")
        for key, chat in chats.items():
            if not isinstance(chat, dict) or chat.get("chat_id") != key:
                raise StateCorruptionError("Chat metadata is corrupt; restore a backup.")
        return chats

    def list(self) -> list[dict]:
        with self.state.lock:
            values = self._chats(self.state.read()).values()
            return deepcopy(
                sorted(
                    (chat for chat in values if not chat.get("deleted_at")),
                    key=lambda chat: (chat["updated_at"], chat["chat_id"]),
                    reverse=True,
                )
            )

    def get(self, chat_id: str) -> dict:
        try:
            UUID(chat_id)
        except ValueError as exc:
            raise ChatNotFoundError("Chat not found") from exc
        with self.state.lock:
            chat = self._chats(self.state.read()).get(chat_id)
            if not chat or chat.get("deleted_at"):
                raise ChatNotFoundError("Chat not found")
            return deepcopy(chat)

    def create(self, title: str | None = None) -> dict:
        title = self._title(title) if title is not None else "New chat"
        stamp = now()
        chat = dict(
            chat_id=str(uuid4()), title=title, created_at=stamp, updated_at=stamp, deleted_at=None
        )
        self.state.update(lambda state: self._chats(state).__setitem__(chat["chat_id"], chat))
        return deepcopy(chat)

    @staticmethod
    def _title(title: str) -> str:
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            raise ValueError("Title must contain between 1 and 200 characters")
        return title.strip()

    def rename(self, chat_id: str, title: str) -> dict:
        title = self._title(title)
        with self.state.lock:
            self.get(chat_id)

            def mutate(state):
                chat = self._chats(state)[chat_id]
                chat.update(title=title, updated_at=now())
                return deepcopy(chat)

            return self.state.update(mutate)

    def messages(self, chat_id: str) -> list[dict]:
        with self.state.lock:
            self.get(chat_id)
            return self.history.records(chat_id)

    def append_message(self, chat_id: str, request_id: str, role: str, content: str, **options):
        """Future orchestration uses this guard so deleted chats cannot be resurrected."""
        with self.state.lock:
            self.get(chat_id)
            record = self.history.append_message(chat_id, request_id, role, content, **options)

            def mutate(state):
                chat = self._chats(state)[chat_id]
                if role == "user" and chat["title"] == "New chat":
                    chat["title"] = " ".join(content.split())[:80] or "New chat"
                chat["updated_at"] = now()

            self.state.update(mutate)
            return record

    def delete(self, chat_id: str) -> None:
        with self.state.lock:
            self.get(chat_id)

            def tombstone(state):
                self._chats(state)[chat_id].update(deleted_at=now(), gc_pending=True)

            self.state.update(tombstone)
            self._collect(chat_id)

    def resume_deletions(self) -> None:
        with self.state.lock:
            for chat in list(self._chats(self.state.read()).values()):
                if chat.get("deleted_at") and chat.get("gc_pending"):
                    self._collect(chat["chat_id"])

    def _collect(self, chat_id: str) -> None:
        # The only deliberate archive rewrite: preserve all other record bytes exactly.
        with self.history.lock:
            self.history.recover()
            if self.history.path.exists():
                original = self.history.path.read_bytes()
                retained = b"".join(
                    line
                    for line in original.splitlines(keepends=True)
                    if json.loads(line).get("chat_id") != chat_id
                )
                if retained != original:
                    backup = self.history.path.with_name(
                        self.history.path.name + f".before-delete-{uuid4()}.bak"
                    )
                    durable_replace(backup, original)
                    durable_replace(self.history.path, retained)

            def forget_memory(state):
                chats = state.get("chats")
                if not isinstance(chats, dict):
                    raise StateCorruptionError("Compaction metadata is corrupt")
                chats.pop(chat_id, None)

            self.compactions.update(forget_memory)
            self.state.update(lambda state: self._chats(state)[chat_id].update(gc_pending=False))
