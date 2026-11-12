"""Explicit application lifetime: exactly one backend writer per local data root."""

from filelock import FileLock, Timeout

from app.config import Settings

from .activity_logger import ActivityLogger
from .chat_store import ChatStore
from .credentials import CredentialStore
from .generation_registry import GenerationRegistry
from .history_store import HistoryStore
from .index_manager import IndexManager
from .settings_store import SettingsStore


class Runtime:
    def __init__(self, settings: Settings, prompt_loader=None):
        self.settings = settings
        settings.initialize_directories()
        self._lock = FileLock(settings.data_dir / ".backend.lock")
        try:
            self._lock.acquire(timeout=0)
        except Timeout as exc:
            raise RuntimeError("Another backend is already using this data directory") from exc
        try:
            self.history = HistoryStore(settings.data_dir / "chat_history.jsonl")
            self.activity = ActivityLogger(settings.data_dir / "system.log.jsonl")
            self.chats = ChatStore(settings.data_dir, self.history)
            self.credentials = CredentialStore(settings.data_dir)
            self.app_settings = SettingsStore(
                settings.data_dir,
                {
                    "context_tokens": settings.context_tokens,
                    "output_tokens": settings.output_tokens,
                    "embedding_model": settings.embedding_model,
                    "embedding_revision": settings.embedding_revision,
                    "ocr_enabled": settings.ocr_enabled,
                    "ocr_languages": settings.ocr_languages,
                },
            )
            persisted = self.app_settings.read()
            for name in (
                "context_tokens",
                "output_tokens",
                "embedding_model",
                "embedding_revision",
                "ocr_enabled",
                "ocr_languages",
            ):
                setattr(settings, name, persisted[name])
            self.chats.resume_deletions()
            self.index = IndexManager(settings, self.activity)
            self.generations = GenerationRegistry(settings.max_concurrent_requests)
            self.compactor = None
            if prompt_loader is not None:
                from .compaction import CompactionManager

                self.compactor = CompactionManager(self, prompt_loader)
            self.activity.emit("application_start")
        except BaseException:
            self._lock.release()
            raise

    def close(self) -> None:
        try:
            self.index.close()
            self.credentials.clear_session()
            self.activity.emit("application_stop")
        finally:
            self._lock.release()
