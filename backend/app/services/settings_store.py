"""Atomic, non-secret provider/runtime preferences."""
from pathlib import Path
from typing import Any

from .state_store import JsonState


class SettingsStore:
    def __init__(self, data_dir: Path, initial: dict[str, Any] | None = None):
        self._defaults = {"schema_version": 1, "provider": "openai", "model": "",
                          "context_tokens": 16000, "output_tokens": 2000,
                          "embedding_model": "intfloat/multilingual-e5-small",
                          "embedding_revision": None, "ocr_enabled": False,
                          "ocr_languages": "eng+fra+fas", "compatible_base_url": None,
                          "compatible_tools": False, "compatible_usage": False}
        if initial:
            self._defaults.update(initial)
            self._defaults["schema_version"] = 1
        self._state = JsonState(data_dir / "state/app_settings.json", self._defaults)

    def read(self) -> dict[str, Any]:
        value = self._state.read()
        return {key: value.get(key, default) for key, default in self._defaults.items()
                if key != "schema_version"}

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = set(self._defaults) - {"schema_version"}
        if not set(changes).issubset(allowed):
            raise ValueError("Unsupported application setting")
        def mutate(value):
            value.update(changes)
        self._state.update(mutate)
        return self.read()
