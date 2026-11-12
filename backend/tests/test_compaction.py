import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.base import ProviderError, ProviderEvent
from app.llm.base import Capabilities, ConversationMessage, GenerationRequest, SourceExcerpt
from app.main import create_app
from app.services.chat_orchestrator import ChatOrchestrator, PreparedTurn


SUMMARY = """## Entities and selected documents
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


@pytest.fixture
def runtime(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        value = client.app.state.runtime
        value.app_settings.update({"model": "memory-model"})
        value.credentials.set("openai", "session-secret")
        yield value


def _messages(runtime, chat_id, count=8, start=0):
    for index in range(start, start + count):
        role = "user" if index % 2 == 0 else "assistant"
        runtime.chats.append_message(chat_id, f"request-{index // 2}", role,
            f"Message {index + 1} with sk-abcdefghijklmnopqrstuvwxyz", completed=True,
            message_id=f"{chat_id[:8]}-message-{index + 1}")


def test_compaction_uses_exact_next_eight_and_commits_versioned_checkpoint(runtime, monkeypatch):
    import app.services.compaction as module
    first = runtime.chats.create()["chat_id"]
    second = runtime.chats.create()["chat_id"]
    _messages(runtime, first)
    _messages(runtime, second, 6)
    captured = {}

    class Adapter:
        def __init__(self, **kwargs): pass
        async def stream(self, generation, key, cancellation):
            captured["key"] = key
            captured["memory"] = generation.memory
            captured["messages"] = [item.message_id for item in generation.tail]
            captured["text"] = " ".join(item.content for item in generation.tail)
            yield ProviderEvent("text", delta=SUMMARY)
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    result = asyncio.run(runtime.compactor.compact_next(first))
    assert result["last_compacted_message_id"] == f"{first[:8]}-message-8"
    assert result["compacted_message_count"] == 8
    assert result["summary_revision"] == 1
    assert result["prompt_version"] == runtime.compactor.prompts.load("compaction").version
    assert captured["messages"] == [f"{first[:8]}-message-{index}" for index in range(1, 9)]
    assert "[REDACTED]" in captured["text"]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in captured["text"]
    assert captured["key"] == "session-secret"
    reported = runtime.compactor.status(first)
    assert reported["state"] == "completed"
    assert reported["summary_revision"] == 1
    assert reported["request_id"]
    relevant_events = [event for event in runtime.activity.store.records()
                       if event.get("request_id") == reported["request_id"]]
    assert [event["event_type"] for event in relevant_events] == [
        "compaction_started", "compaction_completed"]
    assert asyncio.run(runtime.compactor.compact_next(second)) is None
    assert runtime.chats.compactions.read()["chats"].get(second, {}) == {}
    _messages(runtime, first, 8, start=8)
    next_result = asyncio.run(runtime.compactor.compact_next(first))
    assert captured["memory"] == SUMMARY
    assert captured["messages"] == [f"{first[:8]}-message-{index}" for index in range(9, 17)]
    assert next_result["compacted_message_count"] == 16
    assert next_result["summary_revision"] == 2


def test_invalid_or_oversized_summary_does_not_advance_checkpoint(runtime, monkeypatch):
    import app.services.compaction as module
    chat_id = runtime.chats.create()["chat_id"]
    _messages(runtime, chat_id)

    class Adapter:
        def __init__(self, **kwargs): pass
        async def stream(self, generation, key, cancellation):
            yield ProviderEvent("text", delta="not structured memory")
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    with pytest.raises(module.SummaryValidationError):
        asyncio.run(runtime.compactor.compact_next(chat_id))
    assert runtime.chats.compactions.read()["chats"].get(chat_id, {}) == {}


def test_provider_failure_retains_checkpoint_and_compaction_retries_same_batch(runtime, monkeypatch):
    import app.services.compaction as module
    chat_id = runtime.chats.create()["chat_id"]
    _messages(runtime, chat_id)
    attempts = []

    class Adapter:
        def __init__(self, **kwargs): pass
        async def stream(self, generation, key, cancellation):
            attempts.append([message.message_id for message in generation.tail])
            raise ProviderError("network_error", "provider unavailable", retryable=True)
            yield  # Make this an async generator.

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    for _ in range(2):
        with pytest.raises(ProviderError):
            asyncio.run(runtime.compactor.compact_next(chat_id))
    assert attempts == [[f"{chat_id[:8]}-message-{index}" for index in range(1, 9)]] * 2
    assert runtime.chats.compactions.read()["chats"].get(chat_id, {}) == {}


def test_summary_redaction_and_token_budget_validation():
    from app.services.compaction import SummaryValidationError, validate_summary
    safe = validate_summary(SUMMARY + "\nBearer secret-token", token_budget=900)
    assert "[REDACTED]" in safe
    with pytest.raises(SummaryValidationError):
        validate_summary(SUMMARY, token_budget=500, token_counter=lambda _: 501)


def test_revision_race_rejects_stale_summary_without_overwriting_new_checkpoint(runtime, monkeypatch):
    import app.services.compaction as module
    chat_id = runtime.chats.create()["chat_id"]
    _messages(runtime, chat_id)

    class RacingAdapter:
        def __init__(self, **kwargs): pass
        async def stream(self, generation, key, cancellation):
            def race(state):
                state["chats"][chat_id] = {"summary": "newer", "summary_revision": 1,
                    "last_compacted_message_id": f"{chat_id[:8]}-message-1", "compacted_message_count": 1}
            runtime.chats.compactions.update(race)
            yield ProviderEvent("text", delta=SUMMARY)
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", RacingAdapter)
    with pytest.raises(module.CompactionConflictError):
        asyncio.run(runtime.compactor.compact_next(chat_id))
    stored = runtime.chats.compactions.read()["chats"][chat_id]
    assert stored["summary"] == "newer"
    assert stored["summary_revision"] == 1


def test_context_budget_emergency_compacts_oldest_tail_and_preserves_question_and_archive(runtime, monkeypatch):
    import app.services.compaction as module
    chat_id = runtime.chats.create()["chat_id"]
    runtime.app_settings.update({"context_tokens": 4000, "output_tokens": 500,
                                 "model": "budget-model"})
    archived = []
    for index in range(16):
        role = "user" if index % 2 == 0 else "assistant"
        record = runtime.chats.append_message(chat_id, f"history-request-{index // 2}", role,
            f"historical-{index + 1} " + ("x" * 350), message_id=f"history-{index + 1}")
        archived.append(record["content"])
    original_archive = [row["content"] for row in runtime.history.records(chat_id)]
    chunk_id, document_id = str(uuid4()), str(uuid4())
    generation = GenerationRequest(model="budget-model", system="System instructions",
        memory="", tail=tuple(ConversationMessage(f"history-{i+1}",
            "user" if i % 2 == 0 else "assistant", archived[i]) for i in range(16)),
        sources=(SourceExcerpt(chunk_id, document_id, "notes.pdf", 2, 2,
            "Evidence text " + ("e" * 300), "index-v1"),),
        current_message_id=str(uuid4()), current_question="What changed?",
        capabilities=Capabilities(4000, 500), output_tokens=500)
    prepared = PreparedTurn(chat_id, str(uuid4()), generation.current_message_id,
        generation.current_question, generation, generation.current_question, ({
            "chunk_id": chunk_id, "document_id": document_id, "filename": "notes.pdf", "page": 2,
        },))
    batch_sizes = []

    class Adapter:
        def __init__(self, **kwargs): pass
        async def stream(self, request, key, cancellation):
            batch_sizes.append(len(request.tail))
            yield ProviderEvent("text", delta=SUMMARY)
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    runtime.compactor.token_counter = len
    orchestrator = ChatOrchestrator(runtime, runtime.compactor.prompts, token_counter=len)
    fitted = asyncio.run(orchestrator.fit_context(prepared))
    assert len(batch_sizes) > 2
    assert all(1 <= size <= 8 for size in batch_sizes)
    assert sum(batch_sizes) == 14
    assert [item.message_id for item in fitted.generation.tail] == ["history-15", "history-16"]
    assert fitted.generation.current_question == "What changed?"
    assert fitted.generation.current_message_id not in {item.message_id for item in fitted.generation.tail}
    assert orchestrator._budget(fitted.generation).measure(fitted.generation).fits
    assert [row["content"] for row in runtime.history.records(chat_id)] == original_archive


def test_unfit_question_fails_without_compacting_or_truncating(runtime, monkeypatch):
    from app.services.chat_orchestrator import ChatOrchestrator, PreparedTurn
    from app.llm.base import Capabilities, GenerationRequest, ProviderError, SourceExcerpt

    chat_id = runtime.chats.create()["chat_id"]
    runtime.app_settings.update({"context_tokens": 2000, "output_tokens": 500,
                                 "model": "budget-model"})
    current_id, chunk_id, document_id = str(uuid4()), str(uuid4()), str(uuid4())
    question = "Q" * 3000
    generation = GenerationRequest(model="budget-model", system="System instructions", memory="",
        tail=(), sources=(SourceExcerpt(chunk_id, document_id, "notes.pdf", 1, 1,
            "Evidence", "index-v1"),), current_message_id=current_id, current_question=question,
        capabilities=Capabilities(2000, 500), output_tokens=500)
    prepared = PreparedTurn(chat_id, str(uuid4()), current_id, question, generation, question,
                            ({"chunk_id": chunk_id},))

    async def unexpected(*args, **kwargs):
        raise AssertionError("An unfit current question must not trigger remote compaction")
    monkeypatch.setattr(runtime.compactor, "compact_next", unexpected)
    orchestrator = ChatOrchestrator(runtime, runtime.compactor.prompts, token_counter=len)
    with pytest.raises(ProviderError) as failure:
        asyncio.run(orchestrator.fit_context(prepared))
    assert failure.value.category == "context_budget_exceeded"
    assert generation.current_question == question
    assert runtime.history.records(chat_id) == []
