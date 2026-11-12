"""Session-first provider credentials with an explicit OS-keyring opt-in."""
from collections.abc import Callable
from threading import RLock
from typing import Any

from app.llm.base import ProviderError
from .state_store import JsonState

_PROVIDERS = frozenset({"openai", "anthropic", "google", "openai_compatible"})
_SERVICE_NAME = "local-rag-chat"


class CredentialStore:
    """Never writes provider secrets to application files or includes them in reprs.

    A small atomic preference snapshot records only which providers explicitly opted
    into the OS vault. The secret itself is stored only by the platform keyring.
    """

    def __init__(self, data_dir, *, keyring_factory: Callable[[], Any] | None = None):
        self._preferences = JsonState(data_dir / "state/credential_preferences.json",
                                      {"schema_version": 1, "vault_providers": []})
        self._keyring_factory = keyring_factory or self._default_keyring
        self._session: dict[str, str] = {}
        self._lock = RLock()

    @staticmethod
    def _provider(provider: str) -> str:
        if provider not in _PROVIDERS:
            raise ProviderError("invalid_provider", "Select a supported provider")
        return provider

    @staticmethod
    def _default_keyring():
        try:
            import keyring
            return keyring
        except ImportError as exc:
            raise ProviderError("credential_vault_unavailable",
                                "OS credential vault support is unavailable; no key was saved") from exc

    def _vault(self):
        try:
            return self._keyring_factory()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("credential_vault_unavailable",
                                "OS credential vault is unavailable; no plaintext fallback was used") from exc

    def _saved(self, provider: str) -> bool:
        return provider in self._preferences.read().get("vault_providers", [])

    def get(self, provider: str) -> str | None:
        provider = self._provider(provider)
        with self._lock:
            if provider in self._session:
                return self._session[provider]
            if not self._saved(provider):
                return None
            try:
                return self._vault().get_password(_SERVICE_NAME, provider)
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError("credential_vault_unavailable",
                                    "Could not read the opted-in OS credential vault") from exc

    def has_key(self, provider: str) -> bool:
        return self.get(provider) is not None

    def persistence_mode(self, provider: str) -> str:
        provider = self._provider(provider)
        with self._lock:
            return "keyring" if self._saved(provider) else "session"

    def set(self, provider: str, api_key: str, *, persist: bool = False) -> None:
        provider = self._provider(provider)
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderError("missing_key", "Enter a non-empty provider key")
        value = api_key.strip()
        with self._lock:
            was_saved = self._saved(provider)
            if persist:
                vault = self._vault()
                try:
                    vault.set_password(_SERVICE_NAME, provider, value)
                    def mark_saved(state):
                        state["vault_providers"] = sorted(
                            set(state.get("vault_providers", [])) | {provider})
                    self._preferences.update(mark_saved)
                except ProviderError:
                    raise
                except Exception as exc:
                    # Best-effort rollback prevents an untracked secret from being left behind.
                    try:
                        vault.delete_password(_SERVICE_NAME, provider)
                    except Exception:
                        pass
                    raise ProviderError("credential_vault_unavailable",
                                        "Could not save the key in the OS credential vault") from exc
            elif was_saved:
                vault = self._vault()
                try:
                    self._delete_password(vault, provider)
                    self._preferences.update(lambda state: state.update(vault_providers=
                        [item for item in state.get("vault_providers", []) if item != provider]))
                except ProviderError:
                    raise
                except Exception as exc:
                    raise ProviderError("credential_vault_unavailable",
                                        "Could not remove the saved key from the OS credential vault") from exc
            self._session[provider] = value

    @staticmethod
    def _delete_password(vault: Any, provider: str) -> None:
        try:
            vault.delete_password(_SERVICE_NAME, provider)
        except Exception as exc:
            # keyring exposes backend-specific not-found exception classes. Only
            # treat its documented PasswordDeleteError as an absent credential.
            try:
                import keyring.errors
                if isinstance(exc, keyring.errors.PasswordDeleteError):
                    return
            except ImportError:
                pass
            raise

    def remove(self, provider: str) -> None:
        provider = self._provider(provider)
        with self._lock:
            if self._saved(provider):
                vault = self._vault()
                try:
                    self._delete_password(vault, provider)
                    self._preferences.update(lambda state: state.update(vault_providers=
                        [item for item in state.get("vault_providers", []) if item != provider]))
                except ProviderError:
                    raise
                except Exception as exc:
                    raise ProviderError("credential_vault_unavailable",
                                        "Could not remove the key from the OS credential vault") from exc
            self._session.pop(provider, None)

    def clear_session(self) -> None:
        with self._lock:
            self._session.clear()

