import asyncio
import json

import httpx
import pytest

from app.llm.base import (Cancellation, Capabilities, ConversationMessage,
                          GenerationRequest, ProviderError)
from app.llm.gemini import GeminiAdapter


def request(*, tools=False):
    return GenerationRequest("models/gemini-configured", "Canonical system", "memory",
        (ConversationMessage("u1", "user", "Earlier"),
         ConversationMessage("a1", "assistant", "Earlier answer")), (), "u2", "Question",
        Capabilities(32000, 2000, tools=True, usage=True), 500, tools_enabled=tools)


def adapter_for(handler):
    return GeminiAdapter("https://provider.test/v1beta", client_factory=lambda **kw:
                         httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw))


def sse(*items):
    return "".join(f"data: {json.dumps(item)}\n\n" for item in items)


def test_gemini_native_sse_role_mapping_streamed_text_and_usage():
    capture = {}

    def handler(req):
        capture["url"] = str(req.url)
        capture["headers"] = dict(req.headers)
        capture["body"] = json.loads(req.content)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(
            {"candidates": [{"content": {"role": "model", "parts": [{"text": "Bonjour"}]}}]},
            {"candidates": [{"content": {"role": "model", "parts": [{"text": "!"}]},
                             "finishReason": "STOP"}],
             "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 3,
                                "totalTokenCount": 15}}))

    async def scenario():
        events = []
        async for item in adapter_for(handler).stream(request(), "key", Cancellation()):
            events.append(item)
        return events

    result = asyncio.run(scenario())
    assert [item.delta for item in result if item.kind == "text"] == ["Bonjour", "!"]
    usage = next(item.usage for item in result if item.kind == "usage")
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (12, 3, 15)
    assert result[-1].kind == "done"
    assert capture["url"].endswith("/models/gemini-configured:streamGenerateContent?alt=sse")
    assert capture["headers"]["x-goog-api-key"] == "key"
    body = capture["body"]
    assert body["systemInstruction"]["parts"][0]["text"].startswith("Canonical system")
    assert "memory" in body["systemInstruction"]["parts"][0]["text"]
    assert [item["role"] for item in body["contents"]] == ["user", "model", "user"]


def test_gemini_function_call_is_constrained_to_library_tools():
    capture = {}

    def handler(req):
        capture["body"] = json.loads(req.content)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(
            {"candidates": [{"content": {"parts": [{"functionCall": {
                "id": "fc-1", "name": "search_library", "args": {
                    "query": "deadline", "top_k": 5}}}]}, "finishReason": "STOP"}]}))

    async def scenario():
        result = []
        async for item in adapter_for(handler).stream(request(tools=True), "key", Cancellation()):
            result.append(item)
        return result

    result = asyncio.run(scenario())
    call = next(item.tool_call for item in result if item.kind == "tool_call")
    assert (call.name, call.arguments, call.call_id) == (
        "search_library", {"query": "deadline", "top_k": 5}, "fc-1")
    assert {item["name"] for item in capture["body"]["tools"][0]["functionDeclarations"]} == {
        "search_library", "get_source_excerpt"}
    assert result[-1].finish_reason == "tool_calls"


def test_gemini_error_model_validation_and_incomplete_stream():
    def error(req):
        return httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT",
                                                     "message": "never reveal key"}})

    async def failed():
        with pytest.raises(ProviderError) as failure:
            async for _ in adapter_for(error).stream(request(), "secret", Cancellation()):
                pass
        assert failure.value.category == "invalid_argument"
        assert "secret" not in str(failure.value)

    async def invalid_model():
        bad = request()
        object.__setattr__(bad, "model", "../../secret")
        with pytest.raises(ProviderError, match="valid Gemini model"):
            async for _ in adapter_for(lambda req: pytest.fail("invalid model reached network"))\
                    .stream(bad, "key", Cancellation()):
                pass

    def no_terminal(req):
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text=sse({"candidates": [{"content": {"parts": [{"text": "partial"}]}}]}))

    async def incomplete():
        with pytest.raises(ProviderError, match="ended before completion"):
            async for _ in adapter_for(no_terminal).stream(request(), "key", Cancellation()):
                pass

    asyncio.run(failed())
    asyncio.run(invalid_model())
    asyncio.run(incomplete())
