import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.schemas import MessageSubmission
from app.llm.base import Cancellation, ProviderError, ProviderEvent
from app.main import create_app
from app.services.chat_orchestrator import ChatOrchestrator, RetryNotFoundError
from app.services.index_manager import IndexUnavailableError


@pytest.fixture
def prepared_runtime(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        runtime = client.app.state.runtime
        runtime.app_settings.update({"model": "configured-model"})
        chat = runtime.chats.create()
        yield runtime, client.app.state.prompts, chat


def test_user_archive_append_precedes_local_retrieval_failure(prepared_runtime, monkeypatch):
    runtime, prompts, chat = prepared_runtime
    chat_id = chat["chat_id"]
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update({"doc": {"status": "ready", "sha256": "fixture"}})
    )

    def unavailable(query, **kwargs):
        assert runtime.history.records(chat_id)[-1]["content"] == "What about its deadline?"
        raise IndexUnavailableError("fixture unavailable")

    monkeypatch.setattr(runtime.index, "search_library", unavailable)
    body = MessageSubmission(content="What about its deadline?", client_message_id=uuid4())
    with pytest.raises(IndexUnavailableError):
        ChatOrchestrator(runtime, prompts).prepare(chat_id, body)
    saved = runtime.history.records(chat_id)
    assert len(saved) == 1
    assert saved[0]["role"] == "user" and saved[0]["completed"] is True
    assert saved[0]["content"] == "What about its deadline?"


def test_memory_and_recent_tail_resolve_followup_but_question_is_not_duplicated(
    prepared_runtime, monkeypatch
):
    runtime, prompts, chat = prepared_runtime
    chat_id = chat["chat_id"]
    old = runtime.chats.append_message(
        chat_id, "r1", "user", "Explain contract ABC-104", message_id="old-user"
    )
    answer = runtime.chats.append_message(
        chat_id, "r1", "assistant", "The delivery period is 15 days", message_id="old-answer"
    )
    runtime.chats.compactions.update(
        lambda state: state["chats"].update(
            {
                chat_id: {
                    "summary": "Selected contract ABC-104; delivery deadline matters.",
                    "last_compacted_message_id": answer["message_id"],
                    "compacted_message_count": 2,
                }
            }
        )
    )
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update({"fixture": {"status": "ready"}})
    )
    seen = {}

    def search(query, **kwargs):
        seen["query"] = query
        return []

    monkeypatch.setattr(runtime.index, "search_library", search)
    body = MessageSubmission(content="What about its deadline?", client_message_id=uuid4())
    prepared = ChatOrchestrator(runtime, prompts).prepare(chat_id, body)
    assert "ABC-104" in prepared.retrieval_query
    assert "delivery deadline" in seen["query"]
    assert prepared.retrieval_query.endswith("What about its deadline?")
    assert prepared.generation.current_question == "What about its deadline?"
    assert prepared.generation.tail == ()
    assert prepared.generation.memory.startswith("Selected contract")
    assert prepared.generation.current_message_id == str(body.client_message_id)
    assert (
        len([row for row in runtime.history.records(chat_id) if row["content"] == body.content])
        == 1
    )


def test_completed_post_checkpoint_tail_excludes_partial_and_current_question(
    prepared_runtime, monkeypatch
):
    runtime, prompts, chat = prepared_runtime
    chat_id = chat["chat_id"]
    checkpoint = runtime.chats.append_message(
        chat_id, "old", "assistant", "Old archived answer", message_id="checkpoint"
    )
    runtime.chats.compactions.update(
        lambda state: state["chats"].update(
            {
                chat_id: {
                    "summary": "Prior cumulative memory",
                    "last_compacted_message_id": checkpoint["message_id"],
                    "compacted_message_count": 1,
                    "summary_revision": 1,
                }
            }
        )
    )
    runtime.chats.append_message(
        chat_id, "next", "user", "Recent user context", message_id="recent-user"
    )
    runtime.chats.append_message(
        chat_id, "next", "assistant", "Partial response", completed=False, message_id="partial"
    )
    body = MessageSubmission(content="Current question", client_message_id=uuid4())
    prepared = ChatOrchestrator(runtime, prompts).prepare(chat_id, body)
    assert [(message.message_id, message.content) for message in prepared.generation.tail] == [
        ("recent-user", "Recent user context")
    ]
    assert prepared.generation.memory == "Prior cumulative memory"
    assert prepared.generation.current_question == "Current question"
    assert str(body.client_message_id) not in {
        message.message_id for message in prepared.generation.tail
    }


def test_retry_reuses_saved_user_message_and_creates_distinct_request_attempt(prepared_runtime):
    runtime, prompts, chat = prepared_runtime
    chat_id = chat["chat_id"]
    first = ChatOrchestrator(runtime, prompts).prepare(
        chat_id, MessageSubmission(content="Question", client_message_id=uuid4())
    )
    retry = ChatOrchestrator(runtime, prompts).prepare(
        chat_id, MessageSubmission(retry_of_request_id=first.request_id)
    )
    assert retry.user_message_id == first.user_message_id
    assert retry.request_id != first.request_id
    assert retry.question == "Question"
    assert len(runtime.history.records(chat_id)) == 1
    assert (
        next(
            event
            for event in reversed(runtime.activity.store.records())
            if event["event_type"] == "user_request_saved"
        )["retry_of_request_id"]
        == first.request_id
    )


def test_unknown_retry_and_empty_question_are_rejected_without_new_records(prepared_runtime):
    runtime, prompts, chat = prepared_runtime
    with pytest.raises(RetryNotFoundError):
        ChatOrchestrator(runtime, prompts).prepare(
            chat["chat_id"], MessageSubmission(retry_of_request_id=uuid4())
        )
    with pytest.raises(ValueError):
        MessageSubmission(content="  ", client_message_id=uuid4())
    assert runtime.history.records(chat["chat_id"]) == []


def test_empty_library_uses_local_grounded_reply_without_provider_key(prepared_runtime):
    runtime, prompts, chat = prepared_runtime
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"], MessageSubmission(content="Quel est le délai?", client_message_id=uuid4())
    )

    async def scenario():
        return [
            event
            async for event in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation())
        ]

    events = asyncio.run(scenario())
    assert "bibliothèque PDF est vide" in events[0].delta
    records = runtime.history.records(chat["chat_id"])
    assert records[-1]["role"] == "assistant" and records[-1]["completed"] is True
    assert records[-1]["content"] == events[0].delta


def test_provider_deltas_are_saved_exactly_once_only_after_terminal_completion(
    prepared_runtime, monkeypatch
):
    import asyncio

    import app.services.chat_orchestrator as module

    runtime, prompts, chat = prepared_runtime
    chat_id = chat["chat_id"]
    document_id, chunk_id = str(uuid4()), str(uuid4())
    runtime.credentials.set("openai", "session-secret")
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update(
            {document_id: {"status": "ready", "sha256": "fixture"}}
        )
    )
    source = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "filename": "source.pdf",
        "page": 3,
        "text": "Deadline is fifteen days.",
        "index_version": "v1",
    }
    monkeypatch.setattr(runtime.index, "search_library", lambda query, *args, **kwargs: [source])
    monkeypatch.setattr(
        runtime.index,
        "get_source_excerpt",
        lambda identifier: {**source, "page_start": 3, "page_end": 3, "available": True},
    )

    class Adapter:
        def __init__(self, **kwargs):
            pass

        async def stream(self, generation, key, cancellation):
            assert key == "session-secret"
            yield ProviderEvent("text", delta="  Supported ")
            yield ProviderEvent("text", delta=f"answer. [[source:{chunk_id}]]  ")
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat_id, MessageSubmission(content="What is the deadline?", client_message_id=uuid4())
    )

    async def scenario():
        return [
            event
            async for event in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation())
        ]

    events = asyncio.run(scenario())
    assistants = [
        record for record in runtime.history.records(chat_id) if record["role"] == "assistant"
    ]
    assert len(assistants) == 1
    assert assistants[0]["content"] == f"  Supported answer. [[source:{chunk_id}]]  "
    assert assistants[0]["completed"] is True
    assert (
        assistants[0]["metadata"]["citations"][0]["url"] == f"/api/library/{document_id}/pdf#page=3"
    )
    assert any(event.kind == "citation" for event in events)
    assert events[-1].kind == "done"


def test_provider_failure_keeps_partial_output_explicitly_incomplete(prepared_runtime, monkeypatch):
    import asyncio

    import app.services.chat_orchestrator as module

    runtime, prompts, chat = prepared_runtime
    document_id = str(uuid4())
    runtime.credentials.set("openai", "session-secret")
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update(
            {document_id: {"status": "ready", "sha256": "fixture"}}
        )
    )
    monkeypatch.setattr(
        runtime.index,
        "search_library",
        lambda query, **kwargs: [
            {
                "chunk_id": str(uuid4()),
                "document_id": document_id,
                "filename": "source.pdf",
                "page": 1,
                "text": "Evidence",
                "index_version": "v1",
            }
        ],
    )

    class Adapter:
        def __init__(self, **kwargs):
            pass

        async def stream(self, generation, key, cancellation):
            yield ProviderEvent("text", delta="partial")
            raise ProviderError("network_error", "provider unavailable", retryable=True)

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"], MessageSubmission(content="Question", client_message_id=uuid4())
    )

    async def scenario():
        with pytest.raises(ProviderError):
            async for _ in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation()):
                pass

    asyncio.run(scenario())
    assistant = next(
        record
        for record in runtime.history.records(chat["chat_id"])
        if record["role"] == "assistant"
    )
    assert assistant["content"] == "partial"
    assert assistant["completed"] is False
    assert assistant["metadata"]["terminal_reason"] == "network_error"


def test_cancellation_finalizes_partial_assistant_as_incomplete(prepared_runtime, monkeypatch):
    import app.services.chat_orchestrator as module

    runtime, prompts, chat = prepared_runtime
    runtime.credentials.set("openai", "session-secret")
    document_id = str(uuid4())
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update(
            {document_id: {"status": "ready", "sha256": "fixture"}}
        )
    )
    monkeypatch.setattr(
        runtime.index,
        "search_library",
        lambda query, **kwargs: [
            {
                "chunk_id": str(uuid4()),
                "document_id": document_id,
                "filename": "source.pdf",
                "page": 1,
                "text": "Evidence",
                "index_version": "v1",
            }
        ],
    )
    cancellation = Cancellation()
    started = asyncio.Event()

    class Adapter:
        def __init__(self, **kwargs):
            pass

        async def stream(self, generation, key, signal):
            yield ProviderEvent("text", delta="partial response")
            started.set()
            await signal.wait()
            signal.raise_if_cancelled()

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"], MessageSubmission(content="Question", client_message_id=uuid4())
    )

    async def scenario():
        task = asyncio.create_task(
            _collect(ChatOrchestrator(runtime, prompts).respond(prepared, cancellation))
        )
        await started.wait()
        cancellation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assistant = next(
        record
        for record in runtime.history.records(chat["chat_id"])
        if record["role"] == "assistant"
    )
    assert assistant["content"] == "partial response"
    assert assistant["completed"] is False
    assert assistant["metadata"]["terminal_reason"] == "canceled"


def test_optional_library_tool_round_uses_local_dispatch_and_emits_real_status(
    prepared_runtime, monkeypatch
):
    import app.services.chat_orchestrator as module
    from app.llm.base import ToolCall

    runtime, prompts, chat = prepared_runtime
    runtime.credentials.set("openai", "session-secret")
    doc_id, first_id, second_id = str(uuid4()), str(uuid4()), str(uuid4())
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update({doc_id: {"status": "ready", "sha256": "fixture"}})
    )
    first = {
        "chunk_id": first_id,
        "document_id": doc_id,
        "filename": "source.pdf",
        "page": 1,
        "page_end": 1,
        "text": "Initial deadline evidence.",
        "index_version": "v1",
    }
    second = {
        "chunk_id": second_id,
        "document_id": doc_id,
        "filename": "source.pdf",
        "page": 2,
        "page_end": 2,
        "text": "Additional deadline evidence.",
        "index_version": "v1",
    }
    monkeypatch.setattr(
        runtime.index,
        "search_library",
        lambda query, *args, **kwargs: [first] if query == "What is the deadline?" else [second],
    )
    monkeypatch.setattr(
        runtime.index,
        "get_source_excerpt",
        lambda chunk_id: {
            **(first if chunk_id == first_id else second),
            "page_start": 1 if chunk_id == first_id else 2,
            "available": True,
        },
    )

    class Adapter:
        def __init__(self, **kwargs):
            self.rounds = 0

        async def stream(self, generation, key, cancellation):
            self.rounds += 1
            if self.rounds == 1:
                assert generation.tools_enabled is True
                yield ProviderEvent(
                    "tool_call",
                    tool_call=ToolCall(
                        "call-1",
                        "search_library",
                        {"query": "deadline details", "top_k": 1, "document_ids": None},
                    ),
                )
                yield ProviderEvent("done", finish_reason="tool_calls")
            else:
                assert len(generation.tool_exchanges) == 1
                assert generation.tool_exchanges[0].result["sources"][0]["chunk_id"] == second_id
                yield ProviderEvent(
                    "text", delta=f"The details are on page 2. [[source:{second_id}]]"
                )
                yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"],
        MessageSubmission(content="What is the deadline?", client_message_id=uuid4()),
    )

    async def scenario():
        return [
            event
            async for event in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation())
        ]

    events = asyncio.run(scenario())
    assert any(event.kind == "status" and event.stage == "retrieving" for event in events)
    assert any(
        event.kind == "retrieval" and event.sources[0]["chunk_id"] == second_id for event in events
    )
    answer = next(
        record
        for record in runtime.history.records(chat["chat_id"])
        if record["role"] == "assistant"
    )
    assert answer["completed"] is True
    assert answer["metadata"]["tool_rounds"] == 1
    assert answer["metadata"]["citations"][0]["chunk_id"] == second_id


def test_tool_round_limit_is_enforced(prepared_runtime, monkeypatch):
    import app.services.chat_orchestrator as module
    from app.llm.base import ToolCall

    runtime, prompts, chat = prepared_runtime
    runtime.settings.max_tool_rounds = 1
    runtime.credentials.set("openai", "session-secret")
    doc_id = str(uuid4())
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update({doc_id: {"status": "ready", "sha256": "fixture"}})
    )
    source = {
        "chunk_id": str(uuid4()),
        "document_id": doc_id,
        "filename": "source.pdf",
        "page": 1,
        "page_end": 1,
        "text": "Evidence",
        "index_version": "v1",
    }
    monkeypatch.setattr(runtime.index, "search_library", lambda query, *args, **kwargs: [source])
    calls = []

    class Adapter:
        def __init__(self, **kwargs):
            pass

        async def stream(self, generation, key, cancellation):
            calls.append(generation)
            yield ProviderEvent(
                "tool_call",
                tool_call=ToolCall(
                    f"call-{len(calls)}",
                    "search_library",
                    {"query": "more", "top_k": 1, "document_ids": None},
                ),
            )
            yield ProviderEvent("done", finish_reason="tool_calls")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"], MessageSubmission(content="Question", client_message_id=uuid4())
    )

    async def scenario():
        with pytest.raises(ProviderError, match="maximum Library retrieval rounds"):
            async for _ in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation()):
                pass

    asyncio.run(scenario())
    assert len(calls) == 2
    assert runtime.activity.store.records()[-1]["status"] == "tool_round_limit"


def test_model_without_tool_support_falls_back_to_deterministic_initial_retrieval(
    prepared_runtime, monkeypatch
):
    import app.services.chat_orchestrator as module

    runtime, prompts, chat = prepared_runtime
    runtime.credentials.set("openai", "session-secret")
    doc_id, chunk_id = str(uuid4()), str(uuid4())
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update({doc_id: {"status": "ready", "sha256": "fixture"}})
    )
    source = {
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "filename": "source.pdf",
        "page": 1,
        "page_end": 1,
        "text": "Initial local evidence.",
        "index_version": "v1",
    }
    monkeypatch.setattr(runtime.index, "search_library", lambda query, *args, **kwargs: [source])
    monkeypatch.setattr(
        runtime.index,
        "get_source_excerpt",
        lambda _chunk_id: {**source, "page_start": 1, "available": True},
    )
    tools_values = []

    class Adapter:
        def __init__(self, **kwargs):
            pass

        async def stream(self, generation, key, cancellation):
            tools_values.append(generation.tools_enabled)
            if generation.tools_enabled:
                raise ProviderError("invalid_request", "tool schema unsupported", status_code=400)
            yield ProviderEvent(
                "text", delta=f"Supported by the initial source. [[source:{chunk_id}]]"
            )
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"], MessageSubmission(content="Question", client_message_id=uuid4())
    )

    async def scenario():
        return [
            event
            async for event in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation())
        ]

    events = asyncio.run(scenario())
    assert tools_values == [True, False]
    assert events[-1].kind == "done"
    assert runtime.activity.store.records()[-1]["event_type"] == "answer_saved"


def test_compatible_generation_uses_only_the_explicit_saved_endpoint(prepared_runtime, monkeypatch):
    import app.services.chat_orchestrator as module

    runtime, prompts, chat = prepared_runtime
    endpoint = "https://configured.example/v1"
    runtime.app_settings.update(
        {
            "provider": "openai_compatible",
            "model": "custom-model",
            "compatible_base_url": endpoint,
            "compatible_tools": False,
            "compatible_usage": False,
        }
    )
    runtime.credentials.set("openai_compatible", "session-secret")
    doc_id = str(uuid4())
    runtime.index.library.manifest.update(
        lambda state: state["documents"].update({doc_id: {"status": "ready", "sha256": "fixture"}})
    )
    monkeypatch.setattr(
        runtime.index,
        "search_library",
        lambda query, **kwargs: [
            {
                "chunk_id": str(uuid4()),
                "document_id": doc_id,
                "filename": "source.pdf",
                "page": 1,
                "text": "Local evidence",
                "index_version": "v1",
            }
        ],
    )
    selected = []

    class Adapter:
        def __init__(self, base_url, **kwargs):
            selected.append(base_url)

        async def stream(self, generation, key, cancellation):
            assert generation.tools_enabled is False
            yield ProviderEvent("text", delta="The configured endpoint received the request.")
            yield ProviderEvent("done", finish_reason="completed")

    monkeypatch.setattr(module, "OpenAIAdapter", Adapter)
    prepared = ChatOrchestrator(runtime, prompts).prepare(
        chat["chat_id"], MessageSubmission(content="Question", client_message_id=uuid4())
    )

    async def scenario():
        return [
            event
            async for event in ChatOrchestrator(runtime, prompts).respond(prepared, Cancellation())
        ]

    events = asyncio.run(scenario())
    assert selected == [endpoint]
    assert events[-1].kind == "done"


async def _collect(iterator):
    return [event async for event in iterator]
