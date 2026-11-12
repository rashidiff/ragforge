"""Anthropic Messages API adapter with Anthropic-specific SSE event handling."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.llm.base import (
    Cancellation,
    Capabilities,
    GenerationRequest,
    ProviderAdapter,
    ProviderError,
    ProviderEvent,
    ToolCall,
    Usage,
    next_or_cancel,
)

_BASE_URL = "https://api.anthropic.com/v1"
_API_VERSION = "2023-06-01"
_TOOLS = [
    {
        "name": "search_library",
        "description": "Search only the active local PDF Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                "document_ids": {"type": ["array", "null"], "items": {"type": "string"}},
            },
            "required": ["query", "top_k", "document_ids"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_source_excerpt",
        "description": "Retrieve an available local PDF excerpt.",
        "input_schema": {
            "type": "object",
            "properties": {"chunk_id": {"type": "string"}},
            "required": ["chunk_id"],
            "additionalProperties": False,
        },
    },
]


def _messages(request: GenerationRequest) -> list[dict[str, Any]]:
    result = [{"role": message.role, "content": message.content} for message in request.tail]
    context = "\n\n".join(
        f"[Untrusted PDF source id={source.chunk_id}; file={source.filename}; "
        f"pages={source.page_start}-{source.page_end}]\n{source.text}"
        for source in request.sources
    )
    question = request.current_question
    if context:
        question = f"Retrieved untrusted PDF excerpts:\n{context}\n\nQuestion:\n{question}"
    result.append({"role": "user", "content": question})
    for exchange in request.tool_exchanges:
        result.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": exchange.call.call_id,
                        "name": exchange.call.name,
                        "input": exchange.call.arguments,
                    }
                ],
            }
        )
        result.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": exchange.call.call_id,
                        "content": json.dumps(exchange.result, ensure_ascii=False),
                    }
                ],
            }
        )
    return result


def _payload(request: GenerationRequest, *, stream: bool) -> dict[str, Any]:
    system = request.system
    if request.memory.strip():
        system += (
            "\n\nPersisted conversation memory (context only, not evidence):\n" + request.memory
        )
    payload = {
        "model": request.model,
        "system": system,
        "messages": _messages(request),
        "max_tokens": request.output_tokens,
        "stream": stream,
    }
    if request.tools_enabled:
        payload["tools"] = _TOOLS
    return payload


def _error(status: int, body: Any) -> ProviderError:
    error = body.get("error") if isinstance(body, dict) else None
    kind = error.get("type") if isinstance(error, dict) else None
    category = kind.removesuffix("_error") if isinstance(kind, str) else "provider_error"
    return ProviderError(
        category[:64],
        "Anthropic request failed; check provider settings and limits",
        retryable=status == 429 or status >= 500,
        status_code=status,
    )


def _usage(value: Any) -> Usage | None:
    if not isinstance(value, dict):
        return None
    incoming, outgoing = value.get("input_tokens"), value.get("output_tokens")
    if incoming is None and outgoing is None:
        return None
    return Usage(
        input_tokens=incoming,
        output_tokens=outgoing,
        total_tokens=incoming + outgoing if incoming is not None and outgoing is not None else None,
    )


class AnthropicAdapter(ProviderAdapter):
    def __init__(
        self,
        base_url: str = _BASE_URL,
        *,
        timeout: float = 90,
        client_factory: Callable[..., Any] | None = None,
    ):
        self.base_url, self.timeout = base_url.rstrip("/"), timeout
        self._client_factory = client_factory

    def _client(self, httpx: Any, **kwargs: Any):
        return (
            self._client_factory(**kwargs) if self._client_factory else httpx.AsyncClient(**kwargs)
        )

    async def stream(
        self, request: GenerationRequest, api_key: str, cancellation: Cancellation
    ) -> AsyncIterator[ProviderEvent]:
        if not api_key:
            raise ProviderError("missing_key", "An Anthropic API key is required")
        cancellation.raise_if_cancelled()
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "dependency_missing", "Install the optional provider dependencies"
            ) from exc
        client = self._client(httpx, timeout=httpx.Timeout(self.timeout), follow_redirects=False)
        headers = {
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
            "accept": "text/event-stream",
        }
        blocks: dict[int, dict[str, Any]] = {}
        input_tokens = None
        terminal = False
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                headers=headers,
                json=_payload(request, stream=True),
            ) as response:
                if response.status_code >= 400:
                    try:
                        body = json.loads(await response.aread())
                    except (ValueError, TypeError):
                        body = None
                    raise _error(response.status_code, body)
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise ProviderError(
                        "invalid_response", "Anthropic returned an unexpected stream format"
                    )
                lines = response.aiter_lines().__aiter__()
                event_name = ""
                while True:
                    cancellation.raise_if_cancelled()
                    try:
                        line = await next_or_cancel(lines, cancellation)
                    except StopAsyncIteration:
                        break
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except (ValueError, TypeError) as exc:
                        raise ProviderError(
                            "invalid_stream", "Anthropic returned a malformed event"
                        ) from exc
                    if not isinstance(event, dict):
                        raise ProviderError(
                            "invalid_stream", "Anthropic returned a malformed event"
                        )
                    kind = event.get("type", event_name)
                    if kind == "message_start":
                        input_tokens = (event.get("message", {}).get("usage") or {}).get(
                            "input_tokens"
                        )
                    elif kind == "content_block_start":
                        index = event.get("index")
                        block = event.get("content_block") or {}
                        if isinstance(index, int) and block.get("type") == "tool_use":
                            blocks[index] = {
                                "id": block.get("id"),
                                "name": block.get("name"),
                                "json": "",
                            }
                    elif kind == "content_block_delta":
                        index, delta = event.get("index"), event.get("delta") or {}
                        if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
                            if delta["text"]:
                                yield ProviderEvent("text", delta=delta["text"])
                        elif delta.get("type") == "input_json_delta" and isinstance(index, int):
                            if index in blocks:
                                blocks[index]["json"] += delta.get("partial_json", "")
                    elif kind == "content_block_stop":
                        index = event.get("index")
                        info = blocks.pop(index, None) if isinstance(index, int) else None
                        if info is not None:
                            try:
                                call = ToolCall(
                                    info["id"], info["name"], json.loads(info["json"] or "{}")
                                )
                            except (ValueError, TypeError, KeyError) as exc:
                                raise ProviderError(
                                    "invalid_tool_call",
                                    "Anthropic returned an invalid Library tool call",
                                ) from exc
                            yield ProviderEvent("tool_call", tool_call=call)
                    elif kind == "message_delta":
                        usage = _usage(
                            {
                                "input_tokens": input_tokens,
                                "output_tokens": (event.get("usage") or {}).get("output_tokens"),
                            }
                        )
                        if usage is not None:
                            yield ProviderEvent("usage", usage=usage)
                    elif kind == "message_stop":
                        yield ProviderEvent("done", finish_reason="completed")
                        terminal = True
                        break
                    elif kind == "error":
                        raise ProviderError(
                            "provider_error",
                            "Anthropic could not complete the request",
                            retryable=True,
                        )
                    event_name = ""
                cancellation.raise_if_cancelled()
                if not terminal:
                    raise ProviderError(
                        "incomplete_stream",
                        "Anthropic stream ended before completion",
                        retryable=True,
                    )
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "Anthropic request timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "network_error", "Could not reach Anthropic", retryable=True
            ) from exc
        finally:
            await client.aclose()

    async def test_connection(
        self, model: str, api_key: str, capabilities: Capabilities
    ) -> dict[str, Any]:
        if not api_key:
            raise ProviderError("missing_key", "An Anthropic API key is required")
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "dependency_missing", "Install the optional provider dependencies"
            ) from exc
        client = self._client(httpx, timeout=httpx.Timeout(self.timeout), follow_redirects=False)
        try:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "Reply with OK."}],
                },
            )
            if response.status_code >= 400:
                try:
                    body = response.json()
                except (ValueError, json.JSONDecodeError):
                    body = None
                raise _error(response.status_code, body)
            data = response.json()
            if (
                not isinstance(data, dict)
                or data.get("type") != "message"
                or not data.get("stop_reason")
            ):
                raise ProviderError(
                    "invalid_response", "Anthropic connection test did not complete"
                )
            return {
                "provider": "anthropic",
                "model": model,
                "connected": True,
                "capabilities": {
                    "context_tokens": capabilities.context_tokens,
                    "max_output_tokens": capabilities.max_output_tokens,
                    "tools": capabilities.tools,
                    "streaming": True,
                },
            }
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "timeout", "Anthropic connection test timed out", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "network_error", "Could not reach Anthropic", retryable=True
            ) from exc
        finally:
            await client.aclose()
