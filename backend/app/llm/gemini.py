"""Google Gemini generateContent adapter using its native REST/SSE wire protocol."""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import uuid4

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

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FUNCTIONS = [
    {
        "name": "search_library",
        "description": "Search only the active local PDF Library.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING"},
                "top_k": {"type": "INTEGER"},
                "document_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["query", "top_k"],
        },
    },
    {
        "name": "get_source_excerpt",
        "description": "Retrieve an available local PDF excerpt.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"chunk_id": {"type": "STRING"}},
            "required": ["chunk_id"],
        },
    },
]


def _model_name(model: str) -> str:
    name = model.removeprefix("models/")
    if not _MODEL.fullmatch(name):
        raise ProviderError("invalid_model", "Enter a valid Gemini model name")
    return name


def _contents(request: GenerationRequest) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = [
        {"role": "model" if item.role == "assistant" else "user", "parts": [{"text": item.content}]}
        for item in request.tail
    ]
    evidence = "\n\n".join(
        f"[Untrusted PDF source id={source.chunk_id}; file={source.filename}; "
        f"pages={source.page_start}-{source.page_end}]\n{source.text}"
        for source in request.sources
    )
    current = request.current_question
    if evidence:
        current = f"Retrieved untrusted PDF excerpts:\n{evidence}\n\nQuestion:\n{current}"
    result.append({"role": "user", "parts": [{"text": current}]})
    for exchange in request.tool_exchanges:
        result.append(
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": exchange.call.name,
                            "args": exchange.call.arguments,
                            "id": exchange.call.call_id,
                        }
                    }
                ],
            }
        )
        result.append(
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": exchange.call.name,
                            "id": exchange.call.call_id,
                            "response": exchange.result,
                        }
                    }
                ],
            }
        )
    return result


def _payload(request: GenerationRequest) -> dict[str, Any]:
    instruction = request.system
    if request.memory.strip():
        instruction += (
            "\n\nPersisted conversation memory (context only, not evidence):\n" + request.memory
        )
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": instruction}]},
        "contents": _contents(request),
        "generationConfig": {"maxOutputTokens": request.output_tokens},
    }
    if request.tools_enabled:
        payload["tools"] = [{"functionDeclarations": _FUNCTIONS}]
        payload["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
    return payload


def _usage(value: Any) -> Usage | None:
    if not isinstance(value, dict):
        return None
    incoming, outgoing = value.get("promptTokenCount"), value.get("candidatesTokenCount")
    total = value.get("totalTokenCount")
    if incoming is None and outgoing is None and total is None:
        return None
    return Usage(input_tokens=incoming, output_tokens=outgoing, total_tokens=total)


def _error(status: int, body: Any) -> ProviderError:
    error = body.get("error") if isinstance(body, dict) else None
    status_name = error.get("status") if isinstance(error, dict) else None
    category = status_name.lower() if isinstance(status_name, str) else "provider_error"
    return ProviderError(
        category[:64],
        "Gemini request failed; check provider settings and limits",
        retryable=status == 429 or status >= 500,
        status_code=status,
    )


class GeminiAdapter(ProviderAdapter):
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

    def _url(self, model: str, method: str) -> str:
        return f"{self.base_url}/models/{_model_name(model)}:{method}"

    async def stream(
        self, request: GenerationRequest, api_key: str, cancellation: Cancellation
    ) -> AsyncIterator[ProviderEvent]:
        if not api_key:
            raise ProviderError("missing_key", "A Gemini API key is required")
        cancellation.raise_if_cancelled()
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "dependency_missing", "Install the optional provider dependencies"
            ) from exc
        client = self._client(httpx, timeout=httpx.Timeout(self.timeout), follow_redirects=False)
        terminal = False
        tool_call_seen = False
        try:
            async with client.stream(
                "POST",
                self._url(request.model, "streamGenerateContent") + "?alt=sse",
                headers={
                    "x-goog-api-key": api_key,
                    "content-type": "application/json",
                    "accept": "text/event-stream",
                },
                json=_payload(request),
            ) as response:
                if response.status_code >= 400:
                    try:
                        body = json.loads(await response.aread())
                    except (ValueError, TypeError):
                        body = None
                    raise _error(response.status_code, body)
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise ProviderError(
                        "invalid_response", "Gemini returned an unexpected stream format"
                    )
                lines = response.aiter_lines().__aiter__()
                while True:
                    cancellation.raise_if_cancelled()
                    try:
                        line = await next_or_cancel(lines, cancellation)
                    except StopAsyncIteration:
                        break
                    if not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                    except (ValueError, TypeError) as exc:
                        raise ProviderError(
                            "invalid_stream", "Gemini returned a malformed event"
                        ) from exc
                    if not isinstance(data, dict):
                        raise ProviderError("invalid_stream", "Gemini returned a malformed event")
                    if isinstance(data.get("error"), dict):
                        error_code = data["error"].get("code")
                        status = error_code if isinstance(error_code, int) else 502
                        raise _error(status, data)
                    for candidate in data.get("candidates", []):
                        content = candidate.get("content") or {}
                        for part in content.get("parts", []):
                            text = part.get("text")
                            if isinstance(text, str) and text:
                                yield ProviderEvent("text", delta=text)
                            function = part.get("functionCall")
                            if function is not None:
                                if not isinstance(function, dict):
                                    raise ProviderError(
                                        "invalid_tool_call",
                                        "Gemini returned an invalid Library tool call",
                                    )
                                try:
                                    call = ToolCall(
                                        function.get("id") or f"gemini-{uuid4()}",
                                        function["name"],
                                        function.get("args") or {},
                                    )
                                except (ValueError, TypeError, KeyError) as exc:
                                    raise ProviderError(
                                        "invalid_tool_call",
                                        "Gemini returned an invalid Library tool call",
                                    ) from exc
                                tool_call_seen = True
                                yield ProviderEvent("tool_call", tool_call=call)
                        reason = candidate.get("finishReason")
                        if reason and reason not in {"FINISH_REASON_UNSPECIFIED", "UNSPECIFIED"}:
                            usage = _usage(data.get("usageMetadata"))
                            if usage is not None:
                                yield ProviderEvent("usage", usage=usage)
                            if reason not in {"STOP", "MAX_TOKENS"}:
                                raise ProviderError(
                                    "generation_stopped",
                                    "Gemini stopped the response before a usable answer",
                                    retryable=reason in {"OTHER", "RECITATION"},
                                )
                            yield ProviderEvent(
                                "done",
                                finish_reason="tool_calls" if tool_call_seen else reason.lower(),
                            )
                            terminal = True
                            break
                    if terminal:
                        break
                    usage = _usage(data.get("usageMetadata"))
                    # Some REST streams send a final usage-only record after candidates.
                    if usage is not None:
                        yield ProviderEvent("usage", usage=usage)
                cancellation.raise_if_cancelled()
                if not terminal:
                    raise ProviderError(
                        "incomplete_stream", "Gemini stream ended before completion", retryable=True
                    )
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "Gemini request timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network_error", "Could not reach Gemini", retryable=True) from exc
        finally:
            await client.aclose()

    async def test_connection(
        self, model: str, api_key: str, capabilities: Capabilities
    ) -> dict[str, Any]:
        if not api_key:
            raise ProviderError("missing_key", "A Gemini API key is required")
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "dependency_missing", "Install the optional provider dependencies"
            ) from exc
        client = self._client(httpx, timeout=httpx.Timeout(self.timeout), follow_redirects=False)
        try:
            response = await client.post(
                self._url(model, "generateContent"),
                headers={"x-goog-api-key": api_key, "content-type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": "Reply with OK."}]}],
                    "generationConfig": {"maxOutputTokens": 8},
                },
            )
            if response.status_code >= 400:
                try:
                    body = response.json()
                except (ValueError, json.JSONDecodeError):
                    body = None
                raise _error(response.status_code, body)
            data = response.json()
            candidates = data.get("candidates") if isinstance(data, dict) else None
            if not candidates or not candidates[0].get("finishReason"):
                raise ProviderError("invalid_response", "Gemini connection test did not complete")
            return {
                "provider": "google",
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
                "timeout", "Gemini connection test timed out", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network_error", "Could not reach Gemini", retryable=True) from exc
        finally:
            await client.aclose()
