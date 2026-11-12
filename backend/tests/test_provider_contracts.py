import asyncio
from dataclasses import replace

import pytest

from app.llm.base import (Cancellation, Capabilities, ConversationMessage, GenerationRequest,
                          ProviderError, ProviderEvent, SourceExcerpt, ToolCall, Usage)


def request():
    return GenerationRequest(model="configured-model", system="Canonical prompt", memory="",
                             tail=(), sources=(), current_message_id="current", current_question="  فارسی\nquestion  ",
                             capabilities=Capabilities(16000, 2000), output_tokens=1000)


def test_current_question_is_preserved_once_and_budget_is_explicit():
    original = request()
    assert original.current_question == "  فارسی\nquestion  "
    with pytest.raises(ValueError, match="exactly once"):
        replace(original, tail=(ConversationMessage("current", "user", original.current_question),))
    with pytest.raises(ValueError):
        replace(original, output_tokens=5000)


def test_tools_require_capability_and_only_library_operations_are_allowed():
    with pytest.raises(ProviderError) as failure:
        replace(request(), tools_enabled=True)
    assert failure.value.category == "unsupported_tools"
    with pytest.raises(ValueError):
        ToolCall("call", "shell", {"command": "ignored"})
    assert ToolCall("call", "search_library", {"query": "deadline", "top_k": 6}).name == "search_library"


def test_stream_events_never_claim_missing_usage_or_missing_deltas():
    assert ProviderEvent("text", delta="actual delta").delta == "actual delta"
    with pytest.raises(ValueError):
        ProviderEvent("text")
    with pytest.raises(ValueError):
        ProviderEvent("usage")
    with pytest.raises(ValueError):
        Usage(input_tokens=-1)
    assert Usage().total_tokens is None


def test_cancellation_propagates_instead_of_false_completion():
    async def scenario():
        cancellation = Cancellation()
        cancellation.cancel()
        await cancellation.wait()
        with pytest.raises(asyncio.CancelledError):
            cancellation.raise_if_cancelled()
    asyncio.run(scenario())


def test_source_requires_one_based_pages():
    with pytest.raises(ValueError):
        SourceExcerpt("chunk", "doc", "file.pdf", 0, 1, "text", "version")
