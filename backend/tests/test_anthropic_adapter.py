import asyncio
import json

import httpx
import pytest

from app.llm.anthropic import AnthropicAdapter
from app.llm.base import (
    Cancellation,
    Capabilities,
    ConversationMessage,
    GenerationRequest,
    ProviderError,
)


def request(*, tools=False):
    return GenerationRequest(
        "configured-model",
        "Canonical system",
        "persisted memory",
        (ConversationMessage("u1", "user", "Earlier"),),
        (),
        "u2",
        "Question",
        Capabilities(16000, 2000, tools=True, usage=True),
        500,
        tools_enabled=tools,
    )


def adapter_for(handler):
    return AnthropicAdapter(
        "https://provider.test/v1",
        client_factory=lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw),
    )


def events(*items):
    return "".join(f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in items)


def test_anthropic_sse_uses_message_protocol_and_actual_text_deltas():
    capture = {}

    def handler(req):
        capture["headers"] = dict(req.headers)
        capture["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=events(
                {"type": "message_start", "message": {"usage": {"input_tokens": 14}}},
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "réponse"},
                },
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": 8},
                },
                {"type": "message_stop"},
            ),
        )

    async def scenario():
        result = []
        async for item in adapter_for(handler).stream(request(), "private-key", Cancellation()):
            result.append(item)
        return result

    result = asyncio.run(scenario())
    assert [item.delta for item in result if item.kind == "text"] == ["réponse"]
    usage = next(item.usage for item in result if item.kind == "usage")
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (14, 8, 22)
    assert result[-1].kind == "done"
    assert capture["headers"]["x-api-key"] == "private-key"
    assert capture["headers"]["anthropic-version"] == "2023-06-01"
    assert capture["body"]["system"].startswith("Canonical system")
    assert "persisted memory" in capture["body"]["system"]


def test_anthropic_tool_json_is_accumulated_from_provider_deltas():
    def handler(req):
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=events(
                {
                    "type": "content_block_start",
                    "index": 2,
                    "content_block": {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "get_source_excerpt",
                    },
                },
                {
                    "type": "content_block_delta",
                    "index": 2,
                    "delta": {"type": "input_json_delta", "partial_json": '{"chunk_id":"c1"}'},
                },
                {"type": "content_block_stop", "index": 2},
                {"type": "message_stop"},
            ),
        )

    async def scenario():
        result = []
        async for item in adapter_for(handler).stream(request(tools=True), "key", Cancellation()):
            result.append(item)
        return result

    result = asyncio.run(scenario())
    tool = next(item.tool_call for item in result if item.kind == "tool_call")
    assert (tool.name, tool.arguments, tool.call_id) == (
        "get_source_excerpt",
        {"chunk_id": "c1"},
        "tool-1",
    )


def test_anthropic_errors_and_missing_terminal_are_safe_and_incomplete():
    def bad_request(req):
        return httpx.Response(
            429,
            json={
                "type": "error",
                "error": {"type": "rate_limit_error", "message": "do not echo api-key"},
            },
        )

    async def failed():
        with pytest.raises(ProviderError) as failure:
            async for _ in adapter_for(bad_request).stream(request(), "api-key", Cancellation()):
                pass
        assert failure.value.category == "rate_limit"
        assert "api-key" not in str(failure.value)
        assert failure.value.retryable

    def no_terminal(req):
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=events(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "partial"},
                }
            ),
        )

    async def incomplete():
        with pytest.raises(ProviderError, match="ended before completion"):
            async for _ in adapter_for(no_terminal).stream(request(), "key", Cancellation()):
                pass

    asyncio.run(failed())
    asyncio.run(incomplete())
