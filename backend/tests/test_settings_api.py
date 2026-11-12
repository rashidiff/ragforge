from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import create_app
from app.services.credentials import CredentialStore


class Vault:
    def __init__(self):
        self.values = {}
    def get_password(self, service, username):
        return self.values.get((service, username))
    def set_password(self, service, username, password):
        self.values[(service, username)] = password
    def delete_password(self, service, username):
        self.values.pop((service, username), None)


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8000") as connection:
        yield connection


def test_settings_are_persisted_but_secrets_are_write_only(client):
    secret = "provider-secret-never-return"
    saved = client.put("/api/settings", json={"provider": "openai", "model": "editable-model",
        "api_key": secret, "context_tokens": 12000, "output_tokens": 1000})
    assert saved.status_code == 200
    assert saved.json()["has_key"] is True
    assert saved.json()["persistence_mode"] == "session"
    assert secret not in saved.text
    assert client.get("/api/settings").json()["model"] == "editable-model"
    assert secret not in (client.app.state.runtime.settings.data_dir / "state/app_settings.json").read_text()
    assert secret not in (client.app.state.runtime.settings.data_dir / "system.log.jsonl").read_text()


def test_invalid_budget_and_conflicting_key_actions_do_not_mutate_settings(client):
    before = client.get("/api/settings").json()
    invalid = client.put("/api/settings", json={"context_tokens": 1024, "output_tokens": 800})
    assert invalid.status_code == 422
    conflict = client.put("/api/settings", json={"api_key": "private", "remove_key": True})
    assert conflict.status_code == 422
    assert client.get("/api/settings").json() == before


def test_embedding_change_is_persisted_and_marks_rebuild_required(client):
    response = client.put("/api/settings", json={"embedding_model": "new-local-embedding"})
    assert response.status_code == 200
    assert response.json()["embedding_model"] == "new-local-embedding"
    assert client.app.state.runtime.index.settings.embedding_model == "new-local-embedding"
    # An empty Library has no old vectors to rebuild; populated Libraries expose the mismatch.


def test_keyring_opt_in_and_removal_use_vault_only(client):
    runtime = client.app.state.runtime
    vault = Vault()
    runtime.credentials = CredentialStore(runtime.settings.data_dir, keyring_factory=lambda: vault)
    key = "vault-secret"
    response = client.put("/api/settings", json={"provider": "anthropic", "api_key": key,
                                                   "persist_key": True})
    assert response.status_code == 200
    assert response.json()["persistence_mode"] == "keyring"
    assert key not in response.text
    assert key not in (runtime.settings.data_dir / "state/credential_preferences.json").read_text()
    removed = client.put("/api/settings", json={"remove_key": True})
    assert removed.status_code == 200
    assert removed.json()["has_key"] is False
    assert vault.values == {}


def test_connection_test_calls_selected_real_adapter_without_echoing_key(client, monkeypatch):
    from app.api import settings as settings_api

    class Adapter:
        def __init__(self, **kwargs):
            pass
        async def test_connection(self, model, api_key, capabilities):
            assert (model, api_key) == ("chosen-model", "session-secret")
            return {"provider": "google", "model": model, "connected": True,
                    "capabilities": {"streaming": True, "tools": capabilities.tools}}

    monkeypatch.setitem(settings_api._ADAPTERS, "google", Adapter)
    configured = client.put("/api/settings", json={"provider": "google", "model": "chosen-model",
                                                     "api_key": "session-secret"})
    assert configured.status_code == 200
    result = client.post("/api/settings/test-connection")
    assert result.status_code == 200
    assert result.json()["connected"] is True
    assert "session-secret" not in result.text


def test_connection_errors_are_categorized_and_missing_key_does_not_call_provider(client, monkeypatch):
    from app.api import settings as settings_api
    from app.llm.base import ProviderError

    configured = client.put("/api/settings", json={"provider": "openai", "model": "chosen-model"})
    assert configured.status_code == 200
    missing = client.post("/api/settings/test-connection")
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "missing_key"

    class RateLimited:
        def __init__(self, **kwargs):
            pass
        async def test_connection(self, model, api_key, capabilities):
            raise ProviderError("provider_error", "OpenAI request failed", retryable=True, status_code=429)

    monkeypatch.setitem(settings_api._ADAPTERS, "openai", RateLimited)
    client.put("/api/settings", json={"api_key": "safe-key"})
    limited = client.post("/api/settings/test-connection")
    assert limited.status_code == 429
    assert limited.json()["error"]["retryable"] is True
    assert "safe-key" not in limited.text


def test_compatible_endpoint_requires_secure_or_loopback_url(client):
    invalid = client.put("/api/settings", json={"provider": "openai_compatible",
        "compatible_base_url": "http://remote.example/v1", "model": "custom-model"})
    assert invalid.status_code == 422
    credentials = client.put("/api/settings", json={"provider": "openai_compatible",
        "compatible_base_url": "https://user:password@provider.example/v1",
        "model": "custom-model"})
    assert credentials.status_code == 422
    valid = client.put("/api/settings", json={"provider": "openai_compatible",
        "compatible_base_url": "https://provider.example/v1", "model": "custom-model",
        "api_key": "private-token", "compatible_tools": True, "compatible_usage": True})
    assert valid.status_code == 200
    assert valid.json()["compatible_base_url"] == "https://provider.example/v1"
    assert "private-token" not in valid.text


def test_compatible_connection_negotiates_tool_schema_and_usage_profile(client, monkeypatch):
    from app.api import settings as settings_api

    configured = client.put("/api/settings", json={"provider": "openai_compatible",
        "compatible_base_url": "https://llm.example/v1", "compatible_tools": True,
        "compatible_usage": True, "model": "private-model", "api_key": "private-token"})
    assert configured.status_code == 200
    seen = {}

    class CompatibleAdapter:
        def __init__(self, **kwargs):
            seen["endpoint"] = kwargs["base_url"]
        async def test_connection(self, model, api_key, capabilities):
            seen.update(model=model, has_key=api_key == "private-token", tools=capabilities.tools)
            return {"provider": "openai", "model": model, "connected": True,
                "capabilities": {"tools": capabilities.tools, "usage": True, "streaming": True}}

    monkeypatch.setattr(settings_api, "OpenAIAdapter", CompatibleAdapter)
    result = client.post("/api/settings/test-connection")
    assert result.status_code == 200
    assert result.json()["provider"] == "openai_compatible"
    assert result.json()["capabilities"]["protocol"] == "openai-responses"
    assert result.json()["capabilities"]["tools"] is True
    assert seen == {"endpoint": "https://llm.example/v1", "model": "private-model",
                    "has_key": True, "tools": True}
    assert "private-token" not in result.text


def test_compatible_endpoint_tool_schema_rejection_is_recorded_as_no_tool_capability(client, monkeypatch):
    from app.api import settings as settings_api
    from app.llm.base import ProviderError

    client.put("/api/settings", json={"provider": "openai_compatible",
        "compatible_base_url": "https://llm.example/v1", "compatible_tools": True,
        "model": "custom-model", "api_key": "private-token"})
    capabilities_seen = []

    class CompatibleAdapter:
        def __init__(self, **kwargs): pass
        async def test_connection(self, model, api_key, capabilities):
            capabilities_seen.append(capabilities.tools)
            if capabilities.tools:
                raise ProviderError("unsupported_tools", "Tool schema rejected", status_code=400)
            return {"provider": "openai", "model": model, "connected": True,
                "capabilities": {"tools": False, "usage": False, "streaming": True}}

    monkeypatch.setattr(settings_api, "OpenAIAdapter", CompatibleAdapter)
    result = client.post("/api/settings/test-connection")
    assert result.status_code == 200
    assert capabilities_seen == [True, False]
    assert result.json()["capabilities"]["tools"] is False
    assert client.get("/api/settings").json()["compatible_tools"] is False
