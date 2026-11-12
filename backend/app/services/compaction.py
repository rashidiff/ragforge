"""Recursive per-chat compaction with immutable archive and CAS checkpoints."""

import asyncio
import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from app.llm.anthropic import AnthropicAdapter
from app.llm.base import (
    Cancellation,
    Capabilities,
    ConversationMessage,
    GenerationRequest,
    ProviderError,
)
from app.llm.gemini import GeminiAdapter
from app.llm.openai import OpenAIAdapter
from app.services.context_budget import ContextBudget

_HEADINGS = (
    "Entities and selected documents",
    "Enduring conversational facts and uncertainty",
    "User preferences",
    "Decisions and constraints",
    "Unresolved questions",
    "Contradictions",
    "Source pointers",
)
_CREDENTIAL = re.compile(
    r"(?i)\bBearer\s+[^\s,;]+|\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{12,})\b|"
    r"(?:api[_ -]?key|authorization|access[_ -]?token)\s*[:=]\s*[^\s,;]+"
)
_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_LOCKS_GUARD = RLock()


class CompactionConflictError(RuntimeError):
    pass


class SummaryValidationError(ValueError):
    pass


class CompactionRetryUnavailable(RuntimeError):
    pass


def redact_credentials(text: str) -> str:
    return _CREDENTIAL.sub("[REDACTED]", text)


def validate_summary(
    text: str, *, token_budget: int, token_counter: Callable[[str], int] | None = None
) -> str:
    value = redact_credentials(text.strip())
    missing = [
        heading
        for heading in _HEADINGS
        if not re.search(rf"(?m)^##\s+{re.escape(heading)}\s*$", value)
    ]
    if missing:
        raise SummaryValidationError("Compaction response is missing required structured sections")
    counter = token_counter or (lambda content: math.ceil(len(content.encode("utf-8")) / 4))
    if not value:
        raise SummaryValidationError("Compaction response is empty")
    if counter(value) > token_budget:
        raise SummaryValidationError("Compaction response exceeds the configured summary budget")
    return value


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


class CompactionManager:
    def __init__(
        self, runtime, prompt_loader, *, token_counter: Callable[[str], int] | None = None
    ):
        self.runtime, self.prompts = runtime, prompt_loader
        self.token_counter = token_counter
        self._locks = _LOCKS
        self._status_guard = RLock()
        self._statuses: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _set_status(self, chat_id: str, **changes) -> dict:
        with self._status_guard:
            current = self._statuses.setdefault(chat_id, {})
            current.update(changes)
            return dict(current)

    def status(self, chat_id: str) -> dict:
        self.runtime.chats.get(chat_id)
        checkpoint = self.runtime.chats.compactions.read().get("chats", {}).get(chat_id, {})
        records = [
            record
            for record in self.runtime.history.records(chat_id)
            if record.get("completed") is True and record.get("role") in {"user", "assistant"}
        ]
        boundary = checkpoint.get("last_compacted_message_id")
        if boundary:
            position = next(
                (i for i, record in enumerate(records) if record.get("message_id") == boundary),
                None,
            )
            records = records[position + 1 :] if position is not None else records
        with self._status_guard:
            recent = dict(self._statuses.get(chat_id, {}))
        return {
            "chat_id": chat_id,
            "state": recent.get("state", "idle"),
            "summary_revision": checkpoint.get("summary_revision", 0),
            "compacted_message_count": checkpoint.get("compacted_message_count", 0),
            "pending_message_count": len(records),
            "request_id": recent.get("request_id"),
            "provider": recent.get("provider"),
            "model": recent.get("model"),
            "batch_count": recent.get("batch_count", 0),
            "started_at": recent.get("started_at"),
            "completed_at": recent.get("completed_at"),
            "duration_ms": recent.get("duration_ms"),
            "usage": recent.get("usage"),
            "error_category": recent.get("error_category"),
            "retryable": recent.get("state") == "failed",
        }

    def _launch(self, chat_id: str, *, force: bool, batch_size: int) -> asyncio.Task | None:
        with self._status_guard:
            current = self._tasks.get(chat_id)
            if current is not None and not current.done():
                return current
            task = asyncio.create_task(
                self.compact_next(chat_id, force=force, batch_size=batch_size)
            )
            self._tasks[chat_id] = task

        def finished(completed):
            if not completed.cancelled():
                completed.exception()
            with self._status_guard:
                if self._tasks.get(chat_id) is completed:
                    self._tasks.pop(chat_id, None)

        task.add_done_callback(finished)
        return task

    def retry(self, chat_id: str) -> dict:
        current = self.status(chat_id)
        if current["state"] != "failed" or not current["pending_message_count"]:
            raise CompactionRetryUnavailable("There is no failed compaction batch to retry")
        with self._status_guard:
            previous = dict(self._statuses.get(chat_id, {}))
        force = bool(previous.get("force", False))
        batch_size = min(previous.get("batch_count", 8), current["pending_message_count"], 8)
        if not force and batch_size < 8:
            raise CompactionRetryUnavailable("The next regular compaction batch is not complete")
        values = self.runtime.app_settings.read()
        self._set_status(
            chat_id,
            state="queued",
            error_category=None,
            completed_at=None,
            started_clock=None,
            started_at=None,
            request_id=None,
            provider=values["provider"],
            model=values["model"],
            batch_count=batch_size,
        )
        queued = self.status(chat_id)
        self._launch(chat_id, force=force, batch_size=batch_size)
        return queued

    async def _lock_for(self, chat_id: str) -> asyncio.Lock:
        # Event-loop-local manager use; guard construction across concurrent requests.
        key = (id(asyncio.get_running_loop()), chat_id)
        with _LOCKS_GUARD:
            return self._locks.setdefault(key, asyncio.Lock())

    def _next_batch(
        self, chat_id: str, *, batch_size: int, defer_message_id: str | None, force: bool
    ) -> tuple[dict, list[dict]] | None:
        state = self.runtime.chats.compactions.read()
        checkpoint = state.get("chats", {}).get(chat_id, {})
        records = [
            record
            for record in self.runtime.history.records(chat_id)
            if record.get("completed") is True and record.get("role") in {"user", "assistant"}
        ]
        boundary = checkpoint.get("last_compacted_message_id")
        if boundary:
            boundary_index = next(
                (
                    index
                    for index, record in enumerate(records)
                    if record.get("message_id") == boundary
                ),
                None,
            )
            if boundary_index is None:
                raise CompactionConflictError(
                    "The compaction checkpoint no longer matches canonical history"
                )
            records = records[boundary_index + 1 :]
        if defer_message_id:
            deferred = next(
                (
                    index
                    for index, record in enumerate(records)
                    if record.get("message_id") == defer_message_id
                ),
                None,
            )
            if deferred is not None:
                records = records[:deferred]
        if len(records) < batch_size and not (force and records):
            return None
        return checkpoint, records[:batch_size]

    def schedule_if_due(self, chat_id: str) -> asyncio.Task | None:
        """Start one background regular batch after a completed answer, never mid-turn."""
        state = self.runtime.chats.compactions.read().get("chats", {}).get(chat_id, {})
        records = [
            record
            for record in self.runtime.history.records(chat_id)
            if record.get("completed") is True and record.get("role") in {"user", "assistant"}
        ]
        boundary = state.get("last_compacted_message_id")
        if boundary:
            position = next(
                (i for i, record in enumerate(records) if record.get("message_id") == boundary),
                None,
            )
            if position is None:
                raise CompactionConflictError(
                    "The compaction checkpoint no longer matches canonical history"
                )
            records = records[position + 1 :]
        if len(records) < 8:
            return None
        with self._status_guard:
            current = self._statuses.get(chat_id, {})
            task = self._tasks.get(chat_id)
            if (task is not None and not task.done()) or current.get("state") in {
                "queued",
                "running",
            }:
                return task
            values = self.runtime.app_settings.read()
            self._set_status(
                chat_id,
                state="queued",
                batch_count=8,
                force=False,
                provider=values["provider"],
                model=values["model"],
                summary_revision=self.runtime.chats.compactions.read()
                .get("chats", {})
                .get(chat_id, {})
                .get("summary_revision", 0),
                first_message_id=records[0].get("message_id"),
                last_message_id=records[7].get("message_id"),
                started_clock=None,
                started_at=None,
                request_id=None,
                error_category=None,
                completed_at=None,
            )
        return self._launch(chat_id, force=False, batch_size=8)

    async def compact_next(
        self,
        chat_id: str,
        *,
        defer_message_id: str | None = None,
        force: bool = False,
        batch_size: int = 8,
    ) -> dict | None:
        try:
            return await self._compact_next(
                chat_id, defer_message_id=defer_message_id, force=force, batch_size=batch_size
            )
        except asyncio.CancelledError:
            self._finish_failure(chat_id, "canceled")
            raise
        except Exception as exc:
            self._finish_failure(chat_id, getattr(exc, "category", "compaction_failed"))
            raise

    def _finish_failure(self, chat_id: str, category: str) -> None:
        with self._status_guard:
            current = dict(self._statuses.get(chat_id, {}))
        if current.get("state") not in {"queued", "running"}:
            return
        request_id = current.get("request_id") or str(uuid4())
        completed_at = timestamp()
        duration = (
            int((time.monotonic() - current["started_clock"]) * 1000)
            if current.get("started_clock") is not None
            else 0
        )
        if not current.get("request_id"):
            self.runtime.activity.emit(
                "compaction_started",
                chat_id=chat_id,
                request_id=request_id,
                provider=current.get("provider"),
                model=current.get("model"),
                batch_count=current.get("batch_count", 0),
                summary_revision=current.get("summary_revision", 0),
                first_message_id=current.get("first_message_id"),
                last_message_id=current.get("last_message_id"),
            )
        self._set_status(
            chat_id,
            state="failed",
            request_id=request_id,
            error_category=category,
            started_at=current.get("started_at") or completed_at,
            completed_at=completed_at,
            duration_ms=duration,
        )
        self.runtime.activity.emit(
            "compaction_completed",
            chat_id=chat_id,
            request_id=request_id,
            provider=current.get("provider"),
            model=current.get("model"),
            status="canceled" if category == "canceled" else "error",
            duration_ms=duration,
            error_category=category,
        )

    async def _compact_next(
        self, chat_id: str, *, defer_message_id: str | None, force: bool, batch_size: int
    ) -> dict | None:
        if not 1 <= batch_size <= 8 or (batch_size != 8 and not force):
            raise ValueError(
                "Regular compaction consumes exactly eight; emergency batches require force"
            )
        lock = await self._lock_for(chat_id)
        async with lock:
            self.runtime.chats.get(chat_id)
            selected = self._next_batch(
                chat_id, batch_size=batch_size, defer_message_id=defer_message_id, force=force
            )
            if selected is None:
                return None
            checkpoint, batch = selected
            revision = checkpoint.get("summary_revision", 0)
            previous_summary = checkpoint.get("summary", "")
            prior_summary = redact_credentials(
                previous_summary if isinstance(previous_summary, str) else ""
            )
            prompt = self.prompts.load("compaction")
            provider_settings = self.runtime.app_settings.read()
            provider, model = provider_settings["provider"], provider_settings["model"]
            if not model.strip():
                raise ProviderError(
                    "model_required", "Choose a provider model before compacting chat history"
                )
            api_key = self.runtime.credentials.get(provider)
            if not api_key:
                raise ProviderError(
                    "missing_key", "Add a provider API key before compacting chat history"
                )

            token_budget = max(500, min(900, self.runtime.settings.summary_tokens))
            request_id = str(uuid4())
            current_message_id = str(uuid4())
            output_limit = min(provider_settings["output_tokens"], token_budget)
            budget = ContextBudget(
                provider,
                model,
                provider_settings["context_tokens"],
                output_limit,
                token_counter=self.token_counter,
            )
            while True:
                messages = tuple(
                    ConversationMessage(
                        record["message_id"], record["role"], redact_credentials(record["content"])
                    )
                    for record in batch
                )
                generation = GenerationRequest(
                    model=model,
                    system=prompt.text,
                    memory=prior_summary,
                    tail=messages,
                    sources=(),
                    current_message_id=current_message_id,
                    current_question="Return only the recursively updated structured conversation memory.",
                    capabilities=Capabilities(
                        context_tokens=provider_settings["context_tokens"],
                        max_output_tokens=output_limit,
                        tools=False,
                        usage=True,
                        streaming=True,
                    ),
                    output_tokens=output_limit,
                    tools_enabled=False,
                )
                if budget.measure(generation).fits:
                    break
                if not force or len(batch) == 1:
                    raise ProviderError(
                        "context_budget_exceeded",
                        "An archived message batch exceeds the selected model's safe compaction budget.",
                        retryable=True,
                    )
                # Emergency mode can commit a smaller oldest-first batch; the raw
                # archive is never shortened and the remaining records stay in tail.
                batch = batch[:-1]
            if provider == "openai_compatible":
                endpoint = provider_settings.get("compatible_base_url")
                if not endpoint:
                    raise ProviderError(
                        "endpoint_required", "Configure the compatible endpoint in Settings"
                    )
                adapter = OpenAIAdapter(
                    base_url=endpoint, timeout=self.runtime.settings.request_timeout_seconds
                )
            else:
                adapter_class = {
                    "openai": OpenAIAdapter,
                    "anthropic": AnthropicAdapter,
                    "google": GeminiAdapter,
                }[provider]
                adapter = adapter_class(timeout=self.runtime.settings.request_timeout_seconds)
            started = time.monotonic()
            self._set_status(
                chat_id,
                state="running",
                request_id=request_id,
                provider=provider,
                model=model,
                batch_count=len(batch),
                force=force,
                started_at=timestamp(),
                first_message_id=batch[0]["message_id"],
                last_message_id=batch[-1]["message_id"],
                started_clock=started,
                summary_revision=revision,
                completed_at=None,
                duration_ms=None,
                usage=None,
                error_category=None,
            )
            self.runtime.activity.emit(
                "compaction_started",
                chat_id=chat_id,
                request_id=request_id,
                provider=provider,
                model=model,
                batch_count=len(batch),
                first_message_id=batch[0]["message_id"],
                last_message_id=batch[-1]["message_id"],
                summary_revision=revision,
            )
            output, usage = [], None
            async for event in adapter.stream(generation, api_key, Cancellation()):
                if event.kind == "text":
                    output.append(event.delta or "")
                elif event.kind == "usage":
                    usage = event.usage
                elif event.kind == "tool_call" or (
                    event.kind == "done" and event.finish_reason == "tool_calls"
                ):
                    raise ProviderError(
                        "unsupported_tools", "Compaction cannot use retrieval tools"
                    )
                elif event.kind == "done":
                    break
            else:
                raise ProviderError(
                    "incomplete_stream",
                    "Compaction provider stream ended early",
                    retryable=True,
                )

            summary = validate_summary(
                "".join(output), token_budget=token_budget, token_counter=self.token_counter
            )
            completed_at = timestamp()
            updated = {
                "summary": summary,
                "last_compacted_message_id": batch[-1]["message_id"],
                "compacted_message_count": checkpoint.get("compacted_message_count", 0)
                + len(batch),
                "prompt_version": prompt.version,
                "summary_revision": revision + 1,
                "updated_at": completed_at,
                "last_compacted_at": completed_at,
                "last_usage": (
                    {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    if usage
                    else None
                ),
            }

            def commit(state):
                current = state.setdefault("chats", {}).get(chat_id, {})
                if current.get("summary_revision", 0) != revision or current.get(
                    "last_compacted_message_id"
                ) != checkpoint.get("last_compacted_message_id"):
                    raise CompactionConflictError(
                        "Conversation memory changed while compaction was running"
                    )
                state["chats"][chat_id] = updated

            self.runtime.chats.compactions.update(commit)
            self.runtime.activity.emit(
                "compaction_completed",
                chat_id=chat_id,
                request_id=request_id,
                provider=provider,
                model=model,
                status="success",
                duration_ms=int((time.monotonic() - started) * 1000),
                compacted_count=updated["compacted_message_count"],
                summary_revision=updated["summary_revision"],
                usage=updated["last_usage"],
            )
            self._set_status(
                chat_id,
                state="completed",
                summary_revision=updated["summary_revision"],
                compacted_message_count=updated["compacted_message_count"],
                completed_at=completed_at,
                duration_ms=int((time.monotonic() - started) * 1000),
                usage=updated["last_usage"],
                error_category=None,
            )
            return updated
