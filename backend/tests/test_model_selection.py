"""Provider/model selection contracts use isolated state and no external calls."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.schemas import MessageSubmission
from app.main import create_app
from app.services.chat_orchestrator import ChatOrchestrator


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(Settings(_env_file=None, data_dir=tmp_path)), base_url="http://127.0.0.1:8000"
    ) as connection:
        yield connection


def test_model_catalog_is_public_documentation_not_credential_disclosure(client):
    runtime = client.app.state.runtime
    runtime.credentials.set("openai", "fixture-secret-never-exposed")
    response = client.get("/api/settings/models")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["provider"] == "openai"
    assert any(model["id"] == "gpt-4.1" for model in catalog["models"])
    assert catalog["source_url"].startswith("https://developers.openai.com/")
    assert catalog["reviewed_at"] == "2026-11-12"
    assert "fixture-secret-never-exposed" not in response.text


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("openai", "gpt-4.1"),
        ("anthropic", "claude-sonnet-5-5"),
        ("google", "gemini-3.8-flash"),
    ],
)
def test_settings_provider_save_selects_its_own_default_without_model_input(
    client, provider, expected
):
    response = client.put("/api/settings", json={"provider": provider})
    assert response.status_code == 200
    assert response.json()["model"] == expected
    assert client.get("/api/settings/models").json()["provider"] == provider


def test_chat_model_selection_persists_and_next_turn_uses_it_without_rewriting_history(client):
    runtime = client.app.state.runtime
    chat_id = runtime.chats.create()["chat_id"]
    runtime.chats.append_message(chat_id, str(uuid4()), "user", "Original فارسی français")
    archive = runtime.history.path.read_bytes()
    response = client.put(
        "/api/settings/model", json={"provider": "openai", "model": "gpt-4.1-mini"}
    )
    assert response.status_code == 200
    assert client.get("/api/settings").json()["model"] == "gpt-4.1-mini"
    assert runtime.history.path.read_bytes() == archive
    prepared = ChatOrchestrator(runtime, client.app.state.prompts).prepare(
        chat_id, MessageSubmission(content="Next question", client_message_id=uuid4())
    )
    assert prepared.generation.model == "gpt-4.1-mini"


def test_stale_provider_and_invalid_model_cannot_mutate_settings(client):
    before = client.get("/api/settings").json()
    assert (
        client.put(
            "/api/settings/model", json={"provider": "anthropic", "model": "claude-sonnet-5-5"}
        ).status_code
        == 409
    )
    for model in ("", "  ", "not a model"):
        assert (
            client.put(
                "/api/settings/model", json={"provider": "openai", "model": model}
            ).status_code
            == 422
        )
    assert client.get("/api/settings").json() == before


def test_model_and_provider_changes_are_blocked_during_generation(client):
    runtime = client.app.state.runtime
    chat_id = runtime.chats.create()["chat_id"]
    lease = runtime.generations.acquire(chat_id)
    try:
        assert (
            client.put(
                "/api/settings/model", json={"provider": "openai", "model": "gpt-4.1-mini"}
            ).status_code
            == 409
        )
        assert client.put("/api/settings", json={"provider": "google"}).status_code == 409
    finally:
        runtime.generations.release(lease)
    assert (
        client.put(
            "/api/settings/model", json={"provider": "openai", "model": "gpt-4.1-mini"}
        ).status_code
        == 200
    )


def test_custom_endpoint_and_saved_model_ids_remain_usable(client):
    response = client.put(
        "/api/settings",
        json={"provider": "openai_compatible", "compatible_base_url": "https://fixture.example/v1"},
    )
    assert response.status_code == 200
    catalog = client.get("/api/settings/models").json()
    assert catalog["models"] == []
    assert catalog["source_url"] is None
    selected = client.put(
        "/api/settings/model",
        json={"provider": "openai_compatible", "model": "local/custom-model:latest"},
    )
    assert selected.status_code == 200
    assert (
        client.get("/api/settings/models").json()["models"][0]["id"] == "local/custom-model:latest"
    )


def test_existing_custom_model_is_preserved_in_catalog(client):
    client.put("/api/settings", json={"model": "previously-configured-snapshot"})
    catalog = client.get("/api/settings/models").json()
    assert catalog["current_model"] == "previously-configured-snapshot"
    assert any(model["id"] == catalog["current_model"] for model in catalog["models"])
