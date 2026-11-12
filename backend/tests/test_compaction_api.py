import asyncio

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.llm.base import ProviderError
from app.main import create_app


@pytest.fixture
def connection(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client


def test_compaction_status_reports_checkpoint_progress_without_summary(connection):
    runtime = connection.app.state.runtime
    chat = runtime.chats.create()
    for index in range(6):
        runtime.chats.append_message(chat["chat_id"], f"r-{index // 2}",
            "user" if index % 2 == 0 else "assistant", f"private message {index}")
    result = connection.get(f"/api/chats/{chat['chat_id']}/compaction")
    assert result.status_code == 200
    assert result.json()["state"] == "idle"
    assert result.json()["pending_message_count"] == 6
    assert "summary" not in result.json()


def test_failed_compaction_status_is_retryable_and_retry_returns_accepted(connection, monkeypatch):
    import app.services.compaction as module

    runtime = connection.app.state.runtime
    chat = runtime.chats.create()
    chat_id = chat["chat_id"]
    runtime.credentials.set("openai", "session-key")
    runtime.app_settings.update({"model": "compaction-model"})
    for index in range(8):
        runtime.chats.append_message(chat_id, f"r-{index // 2}",
            "user" if index % 2 == 0 else "assistant", f"message {index}")

    class FailingAdapter:
        def __init__(self, **kwargs): pass
        async def stream(self, generation, key, cancellation):
            raise ProviderError("network_error", "provider unavailable", retryable=True)
            yield

    monkeypatch.setattr(module, "OpenAIAdapter", FailingAdapter)

    async def fail_background_attempt():
        task = runtime.compactor.schedule_if_due(chat_id)
        await task

    with pytest.raises(ProviderError):
        asyncio.run(fail_background_attempt())
    failed = connection.get(f"/api/chats/{chat_id}/compaction").json()
    assert failed["state"] == "failed"
    assert failed["retryable"] is True
    assert failed["error_category"] == "network_error"
    assert failed["request_id"]
    assert failed["pending_message_count"] == 8
    assert failed["summary_revision"] == 0

    retried = connection.post(f"/api/chats/{chat_id}/compaction/retry")
    assert retried.status_code == 202
    assert retried.json()["state"] in {"queued", "running"}
    assert retried.json()["summary_revision"] == 0


def test_compaction_retry_rejects_when_there_is_no_failed_batch(connection):
    chat_id = connection.post("/api/chats", json={}).json()["chat_id"]
    response = connection.post(f"/api/chats/{chat_id}/compaction/retry")
    assert response.status_code == 409
