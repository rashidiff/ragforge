import pytest

from app.llm.base import ProviderError
from app.services.credentials import CredentialStore


class MemoryKeyring:
    def __init__(self):
        self.values = {}
        self.fail = False

    def set_password(self, service, username, password):
        if self.fail:
            raise RuntimeError("backend unavailable")
        self.values[(service, username)] = password

    def get_password(self, service, username):
        if self.fail:
            raise RuntimeError("backend unavailable")
        return self.values.get((service, username))

    def delete_password(self, service, username):
        if self.fail:
            raise RuntimeError("backend unavailable")
        self.values.pop((service, username), None)


def make_store(tmp_path, vault):
    return CredentialStore(tmp_path, keyring_factory=lambda: vault)


def test_session_is_default_and_never_written_to_application_state(tmp_path):
    vault = MemoryKeyring()
    store = make_store(tmp_path, vault)
    store.set("openai", "  secret-value  ")
    assert store.get("openai") == "secret-value"
    assert store.persistence_mode("openai") == "session"
    assert vault.values == {}
    prefs = tmp_path / "state/credential_preferences.json"
    assert "secret-value" not in prefs.read_text(encoding="utf-8")


def test_keyring_requires_explicit_opt_in_and_survives_new_store_instance(tmp_path):
    vault = MemoryKeyring()
    store = make_store(tmp_path, vault)
    store.set("anthropic", "persist-me", persist=True)
    assert store.persistence_mode("anthropic") == "keyring"
    restarted = make_store(tmp_path, vault)
    assert restarted.get("anthropic") == "persist-me"
    assert restarted.has_key("anthropic")
    assert "persist-me" not in (tmp_path / "state/credential_preferences.json").read_text()


def test_session_only_replacement_removes_previous_vault_entry(tmp_path):
    vault = MemoryKeyring()
    store = make_store(tmp_path, vault)
    store.set("google", "old", persist=True)
    store.set("google", "new", persist=False)
    assert store.get("google") == "new"
    assert store.persistence_mode("google") == "session"
    assert vault.values == {}


def test_remove_clears_session_and_vault_key(tmp_path):
    vault = MemoryKeyring()
    store = make_store(tmp_path, vault)
    store.set("openai", "secret", persist=True)
    store.remove("openai")
    assert not store.has_key("openai")
    assert store.persistence_mode("openai") == "session"
    assert vault.values == {}


def test_vault_failure_is_reported_without_plaintext_fallback(tmp_path):
    vault = MemoryKeyring()
    vault.fail = True
    store = make_store(tmp_path, vault)
    with pytest.raises(ProviderError, match="OS credential vault") as failure:
        store.set("openai", "never-save", persist=True)
    assert "never-save" not in str(failure.value)
    assert vault.values == {}
    assert not (tmp_path / "state/credential_preferences.json").exists()


def test_invalid_provider_is_rejected(tmp_path):
    store = make_store(tmp_path, MemoryKeyring())
    with pytest.raises(ProviderError, match="supported provider"):
        store.set("untrusted", "key")
