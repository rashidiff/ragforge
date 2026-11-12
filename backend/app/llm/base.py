"""Provider-independent input and streaming contracts; provider wire formats stay in adapters."""
from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal


class ProviderError(RuntimeError):
    def __init__(self, category: str, message: str, *, retryable: bool = False,
                 status_code: int | None = None):
        super().__init__(message)
        self.category, self.retryable, self.status_code = category, retryable, status_code


class Cancellation:
    """A signal the orchestrator can propagate without storing provider credentials."""
    def __init__(self):
        self._event = asyncio.Event()

    def cancel(self):
        self._event.set()

    def raise_if_cancelled(self):
        if self._event.is_set():
            raise asyncio.CancelledError()

    async def wait(self):
        await self._event.wait()


async def next_or_cancel(iterator: AsyncIterator[Any], cancellation: Cancellation):
    """Await one upstream frame while remaining promptly abortable without timing out reads."""
    read_task = asyncio.create_task(anext(iterator))
    cancel_task = asyncio.create_task(cancellation.wait())
    try:
        done, _ = await asyncio.wait({read_task, cancel_task},
                                     return_when=asyncio.FIRST_COMPLETED)
        if cancel_task in done:
            read_task.cancel()
            await asyncio.gather(read_task, return_exceptions=True)
            cancellation.raise_if_cancelled()
        return read_task.result()
    finally:
        if not read_task.done():
            read_task.cancel()
        await asyncio.gather(read_task, return_exceptions=True)
        if not cancel_task.done():
            cancel_task.cancel()
        await asyncio.gather(cancel_task, return_exceptions=True)


@dataclass(frozen=True)
class Capabilities:
    context_tokens: int
    max_output_tokens: int
    tools: bool = False
    usage: bool = False
    streaming: bool = True

    def __post_init__(self):
        if self.context_tokens < 1 or not 0 < self.max_output_tokens < self.context_tokens:
            raise ValueError("Explicit valid model context/output limits are required")


@dataclass(frozen=True)
class ConversationMessage:
    message_id: str
    role: Literal["user", "assistant"]
    content: str

    def __post_init__(self):
        if self.role not in {"user", "assistant"}:
            raise ValueError("History contains only completed conversational roles")


@dataclass(frozen=True)
class SourceExcerpt:
    chunk_id: str
    document_id: str
    filename: str
    page_start: int
    page_end: int
    text: str
    index_version: str

    def __post_init__(self):
        if self.page_start < 1 or self.page_end < self.page_start:
            raise ValueError("Sources require exact one-based page ranges")


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: Literal["search_library", "get_source_excerpt"]
    arguments: dict[str, Any]

    def __post_init__(self):
        if not self.call_id or self.name not in {"search_library", "get_source_excerpt"}:
            raise ValueError("Only Library retrieval tools are permitted")


@dataclass(frozen=True)
class ToolExchange:
    call: ToolCall
    result: dict[str, Any]


@dataclass(frozen=True)
class GenerationRequest:
    model: str
    system: str
    memory: str
    tail: tuple[ConversationMessage, ...]
    sources: tuple[SourceExcerpt, ...]
    current_message_id: str
    current_question: str
    capabilities: Capabilities
    output_tokens: int
    tools_enabled: bool = False
    tool_exchanges: tuple[ToolExchange, ...] = ()

    def __post_init__(self):
        if not self.model.strip() or not self.system.strip() or not self.current_question.strip():
            raise ValueError("Model, canonical instructions and current question are required")
        if self.current_message_id in {message.message_id for message in self.tail}:
            raise ValueError("Current question must be separate from the raw tail, exactly once")
        if not 0 < self.output_tokens <= self.capabilities.max_output_tokens:
            raise ValueError("Requested output exceeds configured model capability")
        if self.tools_enabled and not self.capabilities.tools:
            raise ProviderError("unsupported_tools", "This model does not support tool calling")
        if self.tool_exchanges and not self.tools_enabled:
            raise ValueError("Tool results require explicit supported tool mode")


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self):
        if any(value is not None and value < 0 for value in
               (self.input_tokens, self.output_tokens, self.total_tokens)):
            raise ValueError("Usage cannot be negative")


@dataclass(frozen=True)
class ProviderEvent:
    kind: Literal["text", "tool_call", "usage", "citation", "done", "status", "retrieval"]
    delta: str | None = None
    tool_call: ToolCall | None = None
    usage: Usage | None = None
    citation: dict[str, Any] | None = None
    finish_reason: str | None = None
    stage: str | None = None
    label: str | None = None
    sources: tuple[dict[str, Any], ...] = ()

    def __post_init__(self):
        if self.kind not in {"text", "tool_call", "usage", "citation", "done", "status", "retrieval"}:
            raise ValueError("Unknown provider event")
        if self.kind == "text" and self.delta is None:
            raise ValueError("Text events require an actual upstream delta")
        if self.kind == "tool_call" and self.tool_call is None:
            raise ValueError("Tool events require a complete parsed call")
        if self.kind == "usage" and self.usage is None:
            raise ValueError("Usage events require reported provider usage")
        if self.kind == "status" and (not self.stage or not self.label):
            raise ValueError("Status events require a real stage and label")
        if self.kind == "citation" and self.citation is None:
            raise ValueError("Citation events require validated source metadata")


class ProviderAdapter(ABC):
    """Adapters abort/close their upstream connection on cancellation or disconnect.

    Implementations must parse their own protocol, emit actual deltas, never invent
    usage, and emit done only after a valid provider terminal event. A stream ending
    without done is incomplete. Tool-call termination is not a completed answer.
    Keys are per-call write-only parameters and must not enter reprs, logs, errors,
    request transcripts, or any provider-controlled tool state.
    """
    @abstractmethod
    def stream(self, request: GenerationRequest, api_key: str,
               cancellation: Cancellation) -> AsyncIterator[ProviderEvent]:
        raise NotImplementedError

    @abstractmethod
    async def test_connection(self, model: str, api_key: str,
                              capabilities: Capabilities) -> dict[str, Any]:
        raise NotImplementedError
