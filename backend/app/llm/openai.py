"""OpenAI Responses API adapter.

This module uses HTTP directly so streaming, cancellation, error redaction, and the
logical provider contract stay explicit. Only the two local Library tools are sent.
"""
import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.llm.base import (Cancellation, Capabilities, GenerationRequest,
                          ProviderAdapter, ProviderError, ProviderEvent, ToolCall,
                          Usage, next_or_cancel)


_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_TOOLS = [
    {"type": "function", "name": "search_library",
     "description": "Search only the user's active local PDF Library.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
         "document_ids": {"type": ["array", "null"], "items": {"type": "string"}}},
         "required": ["query", "top_k", "document_ids"], "additionalProperties": False},
     "strict": True},
    {"type": "function", "name": "get_source_excerpt",
     "description": "Retrieve one available excerpt from the pinned local PDF index.",
     "parameters": {"type": "object", "properties": {"chunk_id": {"type": "string"}},
                     "required": ["chunk_id"], "additionalProperties": False},
     "strict": True},
]


def _input_items(request: GenerationRequest) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {"role": message.role, "content": message.content} for message in request.tail
    ]
    source_context = "\n\n".join(
        f"[Untrusted PDF source id={source.chunk_id}; file={source.filename}; "
        f"pages={source.page_start}-{source.page_end}]\n{source.text}"
        for source in request.sources
    )
    current = request.current_question
    if source_context:
        current = f"Retrieved untrusted PDF excerpts:\n{source_context}\n\nQuestion:\n{current}"
    items.append({"role": "user", "content": current})
    for exchange in request.tool_exchanges:
        items.append({"type": "function_call", "call_id": exchange.call.call_id,
                      "name": exchange.call.name,
                      "arguments": json.dumps(exchange.call.arguments, ensure_ascii=False)})
        items.append({"type": "function_call_output", "call_id": exchange.call.call_id,
                      "output": json.dumps(exchange.result, ensure_ascii=False)})
    return items


def _payload(request: GenerationRequest, *, stream: bool) -> dict[str, Any]:
    instructions = request.system
    if request.memory.strip():
        instructions += "\n\nPersisted conversation memory (context only, not evidence):\n" + request.memory
    payload: dict[str, Any] = {
        "model": request.model,
        "instructions": instructions,
        "input": _input_items(request),
        "max_output_tokens": request.output_tokens,
        "stream": stream,
        "store": False,
    }
    if request.tools_enabled:
        payload["tools"] = _TOOLS
        payload["tool_choice"] = "auto"
        payload["parallel_tool_calls"] = False
    return payload


def _usage(event: dict[str, Any]) -> Usage | None:
    value = event.get("response", {}).get("usage") or event.get("usage")
    if not isinstance(value, dict):
        return None
    incoming = value.get("input_tokens", value.get("prompt_tokens"))
    outgoing = value.get("output_tokens", value.get("completion_tokens"))
    return Usage(input_tokens=incoming, output_tokens=outgoing,
                 total_tokens=value.get("total_tokens"))


def _provider_error(status: int, body: Any) -> ProviderError:
    code = "provider_error"
    message = "OpenAI rejected the request"
    if isinstance(body, dict):
        detail = body.get("error")
        if isinstance(detail, dict):
            candidate_code = detail.get("code") or detail.get("type")
            if isinstance(candidate_code, str) and candidate_code.replace("_", "").isalnum():
                code = candidate_code[:64]
            candidate_message = detail.get("message")
            if isinstance(candidate_message, str) and candidate_message:
                # Upstream messages can echo submitted credentials or sensitive request data.
                message = "OpenAI request failed; check provider settings and request limits"
    return ProviderError(code, message, retryable=status == 429 or status >= 500,
                         status_code=status)


class OpenAIAdapter(ProviderAdapter):
    """OpenAI Responses adapter; api_key is used only in the Authorization header."""

    def __init__(self, base_url: str = _DEFAULT_BASE_URL, *, timeout: float = 90,
                 client_factory: Callable[..., Any] | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client_factory = client_factory

    def _client(self, httpx: Any, **kwargs: Any):
        if self._client_factory is not None:
            return self._client_factory(**kwargs)
        return httpx.AsyncClient(**kwargs)

    async def stream(self, request: GenerationRequest, api_key: str,
                     cancellation: Cancellation) -> AsyncIterator[ProviderEvent]:
        if not api_key:
            raise ProviderError("missing_key", "An OpenAI API key is required")
        cancellation.raise_if_cancelled()
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError("dependency_missing", "Install the optional provider dependencies") from exc

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                   "Accept": "text/event-stream"}
        seen_terminal = False
        call_items: dict[str, dict[str, str]] = {}
        client = self._client(httpx, timeout=httpx.Timeout(self.timeout), follow_redirects=False)
        try:
            async with client.stream("POST", f"{self.base_url}/responses", headers=headers,
                                     json=_payload(request, stream=True)) as response:
                if response.status_code >= 400:
                    try:
                        body = json.loads(await response.aread())
                    except (ValueError, TypeError):
                        body = None
                    raise _provider_error(response.status_code, body)
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise ProviderError("invalid_response", "OpenAI returned an unexpected stream format")
                lines = response.aiter_lines().__aiter__()
                while True:
                    cancellation.raise_if_cancelled()
                    try:
                        line = await next_or_cancel(lines, cancellation)
                    except StopAsyncIteration:
                        break
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        event = json.loads(raw)
                    except (ValueError, TypeError) as exc:
                        raise ProviderError("invalid_stream", "OpenAI returned a malformed event") from exc
                    if not isinstance(event, dict):
                        raise ProviderError("invalid_stream", "OpenAI returned a malformed event")
                    event_type = event.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            yield ProviderEvent("text", delta=delta)
                    elif event_type == "response.output_item.added":
                        item = event.get("item")
                        if isinstance(item, dict) and item.get("type") == "function_call":
                            item_id, call_id = item.get("id"), item.get("call_id")
                            if isinstance(item_id, str) and isinstance(call_id, str):
                                call_items[item_id] = {"call_id": call_id,
                                                       "name": item.get("name", ""),
                                                       "arguments": item.get("arguments", "")}
                    elif event_type == "response.function_call_arguments.done":
                        item_id = event.get("item_id")
                        info = call_items.get(item_id) if isinstance(item_id, str) else None
                        if info is None:
                            raise ProviderError("invalid_stream", "OpenAI returned an incomplete tool call")
                        try:
                            arguments = json.loads(event.get("arguments", info["arguments"]))
                            call = ToolCall(info["call_id"], info["name"], arguments)
                        except (ValueError, TypeError, KeyError) as exc:
                            raise ProviderError("invalid_tool_call", "OpenAI returned an invalid Library tool call") from exc
                        yield ProviderEvent("tool_call", tool_call=call)
                    elif event_type == "response.completed":
                        usage = _usage(event)
                        if usage is not None:
                            yield ProviderEvent("usage", usage=usage)
                        yield ProviderEvent("done", finish_reason="completed")
                        seen_terminal = True
                        break
                    elif event_type in {"response.failed", "response.incomplete", "error"}:
                        response_data = event.get("response", {})
                        error = response_data.get("error") or event.get("error") or {}
                        status = error.get("code") if isinstance(error, dict) else None
                        category = status if isinstance(status, str) and status.replace("_", "").isalnum() else "provider_error"
                        raise ProviderError(category[:64], "OpenAI could not complete the request",
                                            retryable=event_type == "response.incomplete")
                cancellation.raise_if_cancelled()
                if not seen_terminal:
                    raise ProviderError("incomplete_stream", "OpenAI stream ended before completion", retryable=True)
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "OpenAI request timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network_error", "Could not reach OpenAI", retryable=True) from exc
        finally:
            await client.aclose()

    async def test_connection(self, model: str, api_key: str,
                              capabilities: Capabilities) -> dict[str, Any]:
        if not api_key:
            raise ProviderError("missing_key", "An OpenAI API key is required")
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError("dependency_missing", "Install the optional provider dependencies") from exc
        client = self._client(httpx, timeout=httpx.Timeout(self.timeout), follow_redirects=False)
        body = {"model": model, "input": "Reply with OK.", "max_output_tokens": 8,
                "store": False, "stream": False}
        if capabilities.tools:
            body.update(tools=_TOOLS, tool_choice="none")
        try:
            response = await client.post(f"{self.base_url}/responses",
                                         headers={"Authorization": f"Bearer {api_key}",
                                                  "Content-Type": "application/json"}, json=body)
            if response.status_code >= 400:
                try:
                    error_body = response.json()
                except (ValueError, json.JSONDecodeError):
                    error_body = None
                raise _provider_error(response.status_code, error_body)
            data = response.json()
            if not isinstance(data, dict) or data.get("status") != "completed":
                raise ProviderError("invalid_response", "OpenAI connection test did not complete")
            usage = _usage(data)
            return {"provider": "openai", "model": model, "connected": True,
                    "capabilities": {"context_tokens": capabilities.context_tokens,
                                     "max_output_tokens": capabilities.max_output_tokens,
                                     "tools": capabilities.tools,
                                     "tool_schema_accepted": capabilities.tools,
                                     "usage": usage is not None,
                                     "streaming": True, "protocol": "openai-responses"}}
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "OpenAI connection test timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network_error", "Could not reach OpenAI", retryable=True) from exc
        finally:
            await client.aclose()
