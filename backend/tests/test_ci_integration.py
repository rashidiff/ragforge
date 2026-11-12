"""Offline integration coverage for the complete local PDF-to-grounded-answer path."""

import asyncio
from typing import ClassVar
import json
import re
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.base import ProviderEvent
from app.main import create_app


class FixtureTokenizer:
    def __call__(self, text, **options):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}


class FixtureEmbeddings:
    tokenizer = FixtureTokenizer()
    identity: ClassVar[dict] = {
        "model": "ci-fixture",
        "revision": None,
        "resolved_revision": "fixture-v1",
        "normalized": True,
    }
    version = "ci-fixture-v1"
    max_document_tokens = 500

    def documents(self, texts):
        return np.asarray([[1.0, 0.0] for _ in texts], dtype="float32")

    def query(self, text):
        return np.asarray([1.0, 0.0], dtype="float32")

    def count_tokens(self, text):
        return len(text.split())


def _pdf_bytes():
    import pymupdf

    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text(
            (72, 72), "Contract CI-204 states that delivery is due within fifteen business days."
        )
        return document.tobytes()


def _events(response_text):
    events = []
    for frame in response_text.replace("\r\n", "\n").split("\n\n"):
        name, payload = None, []
        for line in frame.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                payload.append(line[5:].strip())
        if name and payload:
            events.append((name, json.loads("\n".join(payload))))
    return events


def test_pdf_upload_retrieval_mocked_generation_history_and_logs_are_isolated(
    tmp_path, monkeypatch
):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, embedding_model="ci-fixture"))

    class MockProvider:
        async def stream(self, generation, key, cancellation):
            assert key == "ci-only-mock-credential"
            assert generation.current_question == "What is the delivery deadline in CI-204?"
            assert len(generation.sources) == 1
            source = generation.sources[0]
            assert "fifteen business days" in source.text
            yield ProviderEvent(
                "text",
                delta=(f"The deadline is fifteen business days. [[source:{source.chunk_id}]]"),
            )
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(
        "app.services.chat_orchestrator.OpenAIAdapter", lambda **options: MockProvider()
    )

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        runtime = client.app.state.runtime
        runtime.index.embeddings = FixtureEmbeddings()
        runtime.app_settings.update({"provider": "openai", "model": "ci-mock-model"})
        runtime.credentials.set("openai", "ci-only-mock-credential")

        uploaded = client.post(
            "/api/library/upload", files={"file": ("contract.pdf", _pdf_bytes(), "application/pdf")}
        )
        assert uploaded.status_code == 202
        document_id = uploaded.json()["document"]["document_id"]
        runtime.index._executor.submit(lambda: None).result(timeout=15)
        assert client.get("/api/index/status").json()["ready"] is True

        search_results = runtime.index.search_library("CI-204 delivery deadline", top_k=2)
        assert search_results
        assert search_results[0]["document_id"] == document_id

        chat_id = client.post("/api/chats", json={}).json()["chat_id"]
        streamed = client.post(
            f"/api/chats/{chat_id}/messages/stream",
            json={
                "content": "What is the delivery deadline in CI-204?",
                "client_message_id": str(uuid4()),
            },
        )
        assert streamed.status_code == 200
        frames = _events(streamed.text)
        assert any(name == "citation" for name, _ in frames)
        assert next(payload for name, payload in frames if name == "done")["complete"] is True

        messages = client.get(f"/api/chats/{chat_id}/messages").json()["messages"]
        assert [message["role"] for message in messages] == ["user", "assistant"]
        assert messages[1]["completed"] is True
        assert "fifteen business days" in messages[1]["content"]

        history_file = tmp_path / "chat_history.jsonl"
        activity_file = tmp_path / "system.log.jsonl"
        assert history_file.is_file() and activity_file.is_file()
        assert "ci-only-mock-credential" not in history_file.read_text(encoding="utf-8")
        assert "ci-only-mock-credential" not in activity_file.read_text(encoding="utf-8")
        logged_types = {entry["event_type"] for entry in runtime.activity.store.records()}
        assert "provider_request_completed" in logged_types
        assert "answer_saved" in logged_types


def test_recursive_compaction_uses_mock_provider_and_preserves_archive(tmp_path, monkeypatch):
    summary = """## Entities and selected documents
None recorded
## Enduring conversational facts and uncertainty
None recorded
## User preferences
None recorded
## Decisions and constraints
None recorded
## Unresolved questions
None recorded
## Contradictions
None recorded
## Source pointers
None recorded"""

    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        runtime = client.app.state.runtime
        runtime.credentials.set("openai", "ci-compaction-mock-credential")
        runtime.app_settings.update({"provider": "openai", "model": "ci-mock-model"})
        chat_id = runtime.chats.create()["chat_id"]
        for index in range(8):
            runtime.chats.append_message(
                chat_id,
                f"request-{index // 2}",
                "user" if index % 2 == 0 else "assistant",
                f"Archived fixture message {index + 1}",
                completed=True,
                message_id=f"ci-message-{index + 1}",
            )
        raw_before = runtime.history.records(chat_id)
        sent = {}

        class MockCompactionProvider:
            async def stream(self, generation, key, cancellation):
                sent["key"] = key
                sent["message_ids"] = [message.message_id for message in generation.tail]
                yield ProviderEvent("text", delta=summary)
                yield ProviderEvent("done", finish_reason="completed")

        monkeypatch.setattr(
            "app.services.compaction.OpenAIAdapter", lambda **options: MockCompactionProvider()
        )
        checkpoint = asyncio.run(runtime.compactor.compact_next(chat_id))

        assert checkpoint["compacted_message_count"] == 8
        assert checkpoint["summary_revision"] == 1
        assert sent["key"] == "ci-compaction-mock-credential"
        assert sent["message_ids"] == [f"ci-message-{index}" for index in range(1, 9)]
        assert runtime.history.records(chat_id) == raw_before
        assert runtime.chats.compactions.read()["chats"][chat_id]["summary"] == summary
        event_types = {entry["event_type"] for entry in runtime.activity.store.records()}
        assert "compaction_started" in event_types
        assert "compaction_completed" in event_types
        assert "ci-compaction-mock-credential" not in (tmp_path / "system.log.jsonl").read_text(
            encoding="utf-8"
        )
