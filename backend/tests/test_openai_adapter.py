import asyncio
import json

import httpx
import pytest

from app.llm.base import (
    Cancellation,
    Capabilities,
    ConversationMessage,
    GenerationRequest,
    ProviderError,
)
from app.llm.openai import OpenAIAdapter


def make_request(*, tools=False):
    return GenerationRequest(
        model="configured-model",
        system="Canonical instructions",
        memory="memory context",
        tail=(
            ConversationMessage("u1", "user", "Earlier question"),
            ConversationMessage("a1", "assistant", "Earlier answer"),
        ),
        sources=(),
        current_message_id="u2",
        current_question="Current question",
        capabilities=Capabilities(16000, 2000, tools=True, usage=True),
        output_tokens=700,
        tools_enabled=tools,
    )


def adapter_for(handler):
    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return OpenAIAdapter("https://provider.test/v1", client_factory=factory)


def sse(events):
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


def test_stream_maps_current_responses_events_and_preserves_request_roles():
    captured = {}

    def handler(request):
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(
                [
                    {"type": "response.output_text.delta", "delta": "Actual "},
                    {"type": "response.output_text.delta", "delta": "answer"},
                    {
                        "type": "response.completed",
                        "response": {
                            "usage": {"input_tokens": 22, "output_tokens": 5, "total_tokens": 27}
                        },
                    },
                ]
            ),
        )

    async def scenario():
        result = []
        async for event in adapter_for(handler).stream(make_request(), "secret", Cancellation()):
            result.append(event)
        return result

    events = asyncio.run(scenario())
    assert [event.delta for event in events if event.kind == "text"] == ["Actual ", "answer"]
    assert events[-2].usage.input_tokens == 22
    assert events[-1].kind == "done"
    assert captured["body"]["model"] == "configured-model"
    assert captured["body"]["instructions"].startswith("Canonical instructions")
    assert "memory context" in captured["body"]["instructions"]
    assert [item["role"] for item in captured["body"]["input"]] == ["user", "assistant", "user"]
    assert captured["body"]["input"][-1]["content"] == "Current question"
    assert captured["headers"]["authorization"] == "Bearer secret"
    assert captured["body"]["store"] is False


def test_stream_emits_only_configured_library_tool_and_parses_complete_call():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(
                [
                    {
                        "type": "response.output_item.added",
                        "item": {
                            "type": "function_call",
                            "id": "fc_1",
                            "call_id": "call_1",
                            "name": "search_library",
                            "arguments": "",
                        },
                    },
                    {
                        "type": "response.function_call_arguments.done",
                        "item_id": "fc_1",
                        "arguments": '{"query":"deadline","top_k":4,"document_ids":null}',
                    },
                    {"type": "response.completed", "response": {"usage": None}},
                ]
            ),
        )

    async def scenario():
        result = []
        async for event in adapter_for(handler).stream(
            make_request(tools=True), "secret", Cancellation()
        ):
            result.append(event)
        return result

    events = asyncio.run(scenario())
    tool = next(event.tool_call for event in events if event.kind == "tool_call")
    assert (tool.name, tool.arguments, tool.call_id) == (
        "search_library",
        {"query": "deadline", "top_k": 4, "document_ids": None},
        "call_1",
    )
    assert {tool["name"] for tool in captured["body"]["tools"]} == {
        "search_library",
        "get_source_excerpt",
    }
    assert captured["body"]["parallel_tool_calls"] is False


def test_provider_error_is_categorized_without_echoing_upstream_body_or_key():
    def handler(request):
        return httpx.Response(
            401, json={"error": {"type": "invalid_api_key", "message": "secret leaked secret"}}
        )

    async def scenario():
        with pytest.raises(ProviderError) as failure:
            async for _ in adapter_for(handler).stream(make_request(), "secret", Cancellation()):
                pass
        return failure.value

    error = asyncio.run(scenario())
    assert error.category == "invalid_api_key"
    assert "secret" not in str(error)
    assert error.status_code == 401
    assert error.retryable is False


def test_stream_without_provider_terminal_is_incomplete_and_pre_cancel_aborts():
    async def incomplete():
        def handler(request):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text='data: {"type":"response.output_text.delta","delta":"partial"}\n\n',
            )

        with pytest.raises(ProviderError, match="ended before completion"):
            async for _ in adapter_for(handler).stream(make_request(), "secret", Cancellation()):
                pass

    async def cancelled():
        cancellation = Cancellation()
        cancellation.cancel()
        with pytest.raises(asyncio.CancelledError):
            async for _ in adapter_for(
                lambda request: pytest.fail("cancelled request reached network")
            ).stream(make_request(), "secret", cancellation):
                pass

    asyncio.run(incomplete())
    asyncio.run(cancelled())


def test_connection_check_uses_real_provider_response_and_safe_error_mapping():
    def handler(request):
        body = json.loads(request.content)
        assert body["max_output_tokens"] == 8
        return httpx.Response(200, json={"status": "completed", "output": []})

    async def scenario():
        return await adapter_for(handler).test_connection(
            "configured-model", "secret", Capabilities(16000, 2000, tools=False)
        )

    assert asyncio.run(scenario())["connected"] is True


def test_connection_negotiates_responses_tool_schema_and_observed_usage():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            },
        )

    async def scenario():
        return await adapter_for(handler).test_connection(
            "compatible-model", "secret", Capabilities(16000, 2000, tools=True, usage=True)
        )

    result = asyncio.run(scenario())
    assert {tool["name"] for tool in captured["body"]["tools"]} == {
        "search_library",
        "get_source_excerpt",
    }
    assert captured["body"]["tool_choice"] == "none"
    assert result["capabilities"]["protocol"] == "openai-responses"
    assert result["capabilities"]["tool_schema_accepted"] is True
    assert result["capabilities"]["usage"] is True
