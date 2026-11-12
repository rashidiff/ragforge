"""Durable request preparation and local context-aware retrieval."""

import asyncio
import json
import re
import time
from dataclasses import dataclass, replace
from collections.abc import Callable
from uuid import uuid4

from app.domain.schemas import MessageSubmission
from app.llm.anthropic import AnthropicAdapter
from app.llm.base import (
    Cancellation,
    Capabilities,
    ConversationMessage,
    GenerationRequest,
    ProviderAdapter,
    ProviderError,
    ProviderEvent,
    SourceExcerpt,
    ToolCall,
    ToolExchange,
)
from app.llm.gemini import GeminiAdapter
from app.llm.openai import OpenAIAdapter
from app.services.citation_validator import CitationValidator
from app.services.context_budget import ContextBudget
from app.services.retrieval_tools import RetrievalToolDispatcher, ToolDispatchError


class RetryNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class PreparedTurn:
    chat_id: str
    request_id: str
    user_message_id: str
    question: str
    generation: GenerationRequest
    retrieval_query: str
    retrieval_sources: tuple[dict, ...]


def build_retrieval_query(
    question: str, memory: str, tail: tuple[ConversationMessage, ...], *, max_chars: int = 6000
) -> str:
    """Keep the exact current question and add recent context for entity resolution."""
    context_budget = max(0, max_chars - len(question))
    selected: list[str] = []
    for message in reversed(tail):
        if context_budget <= 0:
            break
        content = message.content.strip()
        if content:
            excerpt = content[-context_budget:]
            selected.append(excerpt)
            context_budget -= len(excerpt)
    if memory.strip() and context_budget > 0:
        selected.append(memory.strip()[-context_budget:])
    selected.reverse()
    return "\n".join([*selected, question]) if selected else question


class ChatOrchestrator:
    """Creates a provider-neutral turn only after the canonical user append succeeds."""

    def __init__(self, runtime, prompt_loader, *, token_counter=None):
        self.runtime = runtime
        self.prompts = prompt_loader
        self.token_counter = token_counter

    def prepare(self, chat_id: str, body: MessageSubmission) -> PreparedTurn:
        self.runtime.chats.get(chat_id)
        records = self.runtime.history.records(chat_id)
        if body.retry_of_request_id is not None:
            original = next(
                (
                    record
                    for record in records
                    if record.get("request_id") == str(body.retry_of_request_id)
                    and record.get("role") == "user"
                ),
                None,
            )
            if original is None:
                raise RetryNotFoundError("Retry target not found")
            question = original["content"]
            user_message_id = original["message_id"]
            request_id = str(uuid4())
            retry_of = str(body.retry_of_request_id)
        else:
            # Persist verbatim before touching local retrieval or a remote provider.
            question = body.content
            user_message_id = str(body.client_message_id)
            request_id = str(uuid4())
            retry_of = None
            self.runtime.chats.append_message(
                chat_id,
                request_id,
                "user",
                question,
                message_id=user_message_id,
                metadata={"attempt": "initial"},
            )

        self.runtime.activity.emit(
            "user_request_saved",
            chat_id=chat_id,
            request_id=request_id,
            message_id=user_message_id,
            user_request=question,
            retry_of_request_id=retry_of,
        )

        memory_state = self.runtime.chats.compactions.read().get("chats", {}).get(chat_id, {})
        memory_value = memory_state.get("summary", "")
        memory = (
            memory_value
            if isinstance(memory_value, str)
            else json.dumps(memory_value, ensure_ascii=False, separators=(",", ":"))
            if memory_value
            else ""
        )
        checkpoint_id = memory_state.get("last_compacted_message_id")
        tail_records = [
            record
            for record in self.runtime.history.records(chat_id)
            if record.get("message_id") != user_message_id and record.get("completed") is True
        ]
        if checkpoint_id:
            checkpoint_index = next(
                (
                    index
                    for index, record in enumerate(tail_records)
                    if record.get("message_id") == checkpoint_id
                ),
                None,
            )
            if checkpoint_index is not None:
                tail_records = tail_records[checkpoint_index + 1 :]
        tail = tuple(
            ConversationMessage(record["message_id"], record["role"], record["content"])
            for record in tail_records
            if record.get("role") in {"user", "assistant"}
        )
        retrieval_query = build_retrieval_query(question, memory, tail)

        manifest = self.runtime.index.library.manifest.read()
        active_documents = [
            document
            for document in manifest.get("documents", {}).values()
            if document.get("status") == "ready"
        ]
        sources = []
        if active_documents:
            sources = self.runtime.index.search_library(
                retrieval_query, top_k=self.runtime.settings.retrieval_snippets
            )
        excerpts = tuple(
            SourceExcerpt(
                chunk_id=source["chunk_id"],
                document_id=source["document_id"],
                filename=source["filename"],
                page_start=source["page"],
                page_end=source.get("page_end", source["page"]),
                text=source["text"],
                index_version=source["index_version"],
            )
            for source in sources
        )

        settings = self.runtime.app_settings.read()
        model = settings["model"]
        compatible = settings["provider"] == "openai_compatible"
        if compatible and not settings.get("compatible_base_url"):
            raise ProviderError(
                "endpoint_required", "Configure the compatible endpoint in Settings"
            )
        tool_capability = settings["compatible_tools"] if compatible else True
        usage_capability = settings["compatible_usage"] if compatible else True
        if sources and not model.strip():
            raise ProviderError(
                "model_required", "Choose a provider model in Settings before asking about PDFs"
            )
        if not model:
            model = "local-evidence-only"
        capabilities = Capabilities(
            context_tokens=settings["context_tokens"],
            max_output_tokens=settings["output_tokens"],
            tools=tool_capability and self.runtime.settings.max_tool_rounds > 0,
            usage=usage_capability,
            streaming=True,
        )
        prompt = self.prompts.load("system")
        generation = GenerationRequest(
            model=model,
            system=prompt.text,
            memory=memory,
            tail=tail,
            sources=excerpts,
            current_message_id=user_message_id,
            current_question=question,
            capabilities=capabilities,
            output_tokens=settings["output_tokens"],
            tools_enabled=tool_capability and self.runtime.settings.max_tool_rounds > 0,
        )
        self.runtime.activity.emit(
            "request_prepared",
            chat_id=chat_id,
            request_id=request_id,
            message_id=user_message_id,
            history_message_count=len(tail),
            memory_present=bool(memory),
            source_ids=[source.chunk_id for source in excerpts],
            index_version=excerpts[0].index_version if excerpts else None,
        )
        return PreparedTurn(
            chat_id,
            request_id,
            user_message_id,
            question,
            generation,
            retrieval_query,
            tuple(sources),
        )

    def _budget(self, generation: GenerationRequest) -> ContextBudget:
        settings = self.runtime.app_settings.read()
        return ContextBudget(
            settings["provider"],
            generation.model,
            generation.capabilities.context_tokens,
            generation.output_tokens,
            token_counter=self.token_counter,
        )

    def _tail_after_checkpoint(
        self, chat_id: str, checkpoint_id: str | None, current_message_id: str
    ) -> tuple[ConversationMessage, ...]:
        records = [
            record
            for record in self.runtime.history.records(chat_id)
            if record.get("completed") is True and record.get("role") in {"user", "assistant"}
        ]
        if checkpoint_id:
            position = next(
                (
                    index
                    for index, record in enumerate(records)
                    if record.get("message_id") == checkpoint_id
                ),
                None,
            )
            if position is None:
                raise ProviderError(
                    "memory_checkpoint_conflict",
                    "Conversation memory no longer matches saved history",
                    retryable=True,
                )
            records = records[position + 1 :]
        return tuple(
            ConversationMessage(record["message_id"], record["role"], record["content"])
            for record in records
            if record.get("message_id") != current_message_id
        )

    async def fit_context(self, prepared: PreparedTurn, *, on_compaction=None) -> PreparedTurn:
        """Bound a model request, preserving its exact question and immutable archive."""
        generation = prepared.generation
        budget = self._budget(generation)
        original_sources = tuple(generation.sources)
        question_only = replace(generation, memory="", tail=(), sources=())
        if not budget.measure(question_only).fits:
            raise ProviderError(
                "context_budget_exceeded",
                "This question exceeds the selected model's safe input budget. "
                "Shorten the question or choose a model with a larger context window.",
                retryable=True,
            )
        sources = list(original_sources)
        # Retrieval is already bounded, but provider prompt framing and model limits
        # may require dropping the lowest-ranked excerpts before touching history.
        while len(sources) > 1:
            candidate = replace(generation, sources=tuple(sources))
            if budget.measure(candidate).fits:
                generation = candidate
                break
            sources.pop()
        if sources and budget.measure(replace(generation, sources=tuple(sources))).fits:
            generation = replace(generation, sources=tuple(sources))

        compactor = getattr(self.runtime, "compactor", None)
        while not budget.measure(generation).fits:
            tail = generation.tail
            # Keep the newest two completed messages as immediate conversational intent.
            emergency_count = min(8, len(tail) - 2)
            if compactor is None or emergency_count < 1:
                break
            if on_compaction is not None:
                on_compaction(emergency_count)
            try:
                checkpoint = await compactor.compact_next(
                    prepared.chat_id,
                    defer_message_id=generation.current_message_id,
                    force=True,
                    batch_size=emergency_count,
                )
            except (RuntimeError, OSError, ValueError):
                # The old checkpoint and archive remain available; report a safe
                # context error below if no safe request fits.
                break
            if checkpoint is None:
                break
            generation = replace(
                generation,
                memory=checkpoint["summary"],
                tail=self._tail_after_checkpoint(
                    prepared.chat_id,
                    checkpoint.get("last_compacted_message_id"),
                    generation.current_message_id,
                ),
            )

        report = budget.measure(generation)
        if not report.fits:
            base = replace(generation, sources=())
            selected_sources: list[SourceExcerpt] = []
            if budget.measure(base).fits:
                for source in original_sources:
                    candidate = replace(base, sources=(*selected_sources, source))
                    if budget.measure(candidate).fits:
                        selected_sources.append(source)
                if selected_sources:
                    generation = replace(base, sources=tuple(selected_sources))
                    report = budget.measure(generation)
        self.runtime.activity.emit(
            "context_budget_evaluated",
            chat_id=prepared.chat_id,
            request_id=prepared.request_id,
            provider=budget.provider,
            model=budget.model,
            context_tokens=report.context_tokens,
            output_reserve=report.output_reserve,
            safety_reserve=report.safety_reserve,
            estimated_input_tokens=report.estimated_input_tokens,
            fits=report.fits,
            retained_sources=len(generation.sources),
            retained_tail=len(generation.tail),
        )
        if not report.fits:
            raise ProviderError(
                "context_budget_exceeded",
                "This question, recent context, and at least one relevant source exceed the selected model's safe input budget. "
                "Shorten the question or choose a model with a larger context window.",
                retryable=True,
            )
        retained = {source.chunk_id for source in generation.sources}
        retrieval_sources = tuple(
            source for source in prepared.retrieval_sources if source.get("chunk_id") in retained
        )
        return replace(prepared, generation=generation, retrieval_sources=retrieval_sources)

    @staticmethod
    def _no_evidence(question: str, library_empty: bool) -> str:
        persian = re.search(r"[\u0600-\u06ff]", question) is not None
        french = re.search(r"[àâçéèêëîïôùûüÿœæ]", question, flags=re.IGNORECASE) is not None or any(
            word in question.casefold().split() for word in ("le", "la", "les", "des", "une", "est")
        )
        if persian:
            return (
                "کتابخانه PDF خالی است. برای دریافت پاسخ مستند، ابتدا یک PDF اضافه کنید."
                if library_empty
                else "در PDFهای فعال کتابخانه، مدرک مرتبطی برای پاسخ به این پرسش پیدا نکردم."
            )
        if french:
            return (
                "La bibliothèque PDF est vide. Ajoutez un PDF pour obtenir une réponse fondée sur vos documents."
                if library_empty
                else "Je n’ai pas trouvé de passage pertinent dans les PDF actifs pour répondre à cette question."
            )
        return (
            "The PDF Library is empty. Add a PDF to get an answer grounded in your documents."
            if library_empty
            else "I couldn't find relevant support in the active PDFs to answer this question."
        )

    async def respond(self, prepared: PreparedTurn, cancellation: Cancellation):
        """Stream normalized model events and commit only an exact successful final."""
        chat_id = prepared.chat_id
        settings = self.runtime.app_settings.read()
        if not prepared.generation.sources:
            manifest = self.runtime.index.library.manifest.read()
            empty = not any(
                document.get("status") == "ready"
                for document in manifest.get("documents", {}).values()
            )
            answer = self._no_evidence(prepared.question, empty)
            self.runtime.chats.append_message(
                chat_id,
                prepared.request_id,
                "assistant",
                answer,
                completed=True,
                metadata={"provider": None, "model": None, "grounded": True},
            )
            self.runtime.activity.emit(
                "answer_saved",
                chat_id=chat_id,
                request_id=prepared.request_id,
                complete=True,
                local_no_evidence=True,
            )
            self._schedule_compaction(chat_id, prepared.request_id)
            yield ProviderEvent("text", delta=answer)
            yield ProviderEvent("done", finish_reason="completed")
            return

        provider = settings["provider"]
        key = self.runtime.credentials.get(provider)
        if not key:
            raise ProviderError("missing_key", "Add a provider API key in Settings")
        adapters: dict[str, Callable[..., ProviderAdapter]] = {"openai": OpenAIAdapter, "anthropic": AnthropicAdapter, "google": GeminiAdapter}
        if provider == "openai_compatible":
            endpoint = settings.get("compatible_base_url")
            if not endpoint:
                raise ProviderError(
                    "endpoint_required", "Configure the compatible endpoint in Settings"
                )
            adapter: ProviderAdapter = OpenAIAdapter(
                base_url=endpoint, timeout=self.runtime.settings.request_timeout_seconds
            )
        else:
            adapter = adapters[provider](timeout=self.runtime.settings.request_timeout_seconds)
        text_parts: list[str] = []
        usage = None
        started = time.monotonic()
        exchanges: list[ToolExchange] = []
        all_sources = list(prepared.generation.sources)
        dispatcher = RetrievalToolDispatcher(self.runtime.index)
        tool_rounds = 0
        self.runtime.activity.emit(
            "provider_request_started",
            chat_id=chat_id,
            request_id=prepared.request_id,
            provider=provider,
            model=prepared.generation.model,
        )
        try:
            while True:
                # Tool results are carried in provider tool-result roles; keeping them
                # out of the baseline source block avoids duplicating retrieved text.
                request_generation = replace(prepared.generation, tool_exchanges=tuple(exchanges))
                if not self._budget(request_generation).measure(request_generation).fits:
                    raise ProviderError(
                        "context_budget_exceeded",
                        "Additional Library results exceed the selected model's safe input budget. Retry with a narrower question or fewer sources.",
                        retryable=True,
                    )
                calls: list[ToolCall] = []
                saw_event = False
                try:
                    async for event in adapter.stream(request_generation, key, cancellation):
                        saw_event = True
                        if event.kind == "text":
                            text_parts.append(event.delta or "")
                        elif event.kind == "usage":
                            usage = event.usage
                        elif event.kind == "tool_call":
                            if event.tool_call is None:
                                raise ProviderError("invalid_tool_call", "Provider returned an empty tool call")
                            calls.append(event.tool_call)
                        elif event.kind == "done" and event.finish_reason == "tool_calls":
                            continue
                        elif event.kind == "done":
                            answer = "".join(text_parts)
                            if not answer.strip():
                                raise ProviderError(
                                    "empty_response", "The provider returned no answer"
                                )
                            citations = CitationValidator(self.runtime.index).validate(
                                answer, tuple(all_sources)
                            )
                            duration_ms = int((time.monotonic() - started) * 1000)
                            self.runtime.chats.append_message(
                                chat_id,
                                prepared.request_id,
                                "assistant",
                                answer,
                                completed=True,
                                metadata={
                                    "provider": provider,
                                    "model": prepared.generation.model,
                                    "duration_ms": duration_ms,
                                    "citations": citations,
                                    "tool_rounds": tool_rounds,
                                },
                            )
                            self.runtime.activity.emit(
                                "provider_request_completed",
                                chat_id=chat_id,
                                request_id=prepared.request_id,
                                provider=provider,
                                model=prepared.generation.model,
                                status="success",
                                duration_ms=duration_ms,
                                usage=(
                                    {
                                        "input_tokens": usage.input_tokens,
                                        "output_tokens": usage.output_tokens,
                                        "total_tokens": usage.total_tokens,
                                    }
                                    if usage
                                    else None
                                ),
                                tool_rounds=tool_rounds,
                            )
                            self.runtime.activity.emit(
                                "answer_saved",
                                chat_id=chat_id,
                                request_id=prepared.request_id,
                                complete=True,
                            )
                            self._schedule_compaction(chat_id, prepared.request_id)
                            for citation in citations:
                                yield ProviderEvent("citation", citation=citation)
                            yield event
                            return
                        else:
                            yield event
                except ProviderError as exc:
                    # A model that rejects tool schemas can still answer from deterministic
                    # initial retrieval. Retry only before any response/tool exchange exists.
                    if (
                        request_generation.tools_enabled
                        and not exchanges
                        and not text_parts
                        and not saw_event
                        and exc.status_code == 400
                    ):
                        request_generation = replace(request_generation, tools_enabled=False)
                        self.runtime.activity.emit(
                            "provider_tools_unavailable",
                            chat_id=chat_id,
                            request_id=prepared.request_id,
                            provider=provider,
                            model=prepared.generation.model,
                            status_code=exc.status_code,
                        )
                        async for event in adapter.stream(request_generation, key, cancellation):
                            if event.kind == "tool_call":
                                raise ProviderError(
                                    "unsupported_tools", "Provider rejected retrieval tools"
                                )
                            if event.kind == "text":
                                text_parts.append(event.delta or "")
                            elif event.kind == "usage":
                                usage = event.usage
                            elif event.kind == "done":
                                answer = "".join(text_parts)
                                if not answer.strip():
                                    raise ProviderError(
                                        "empty_response", "The provider returned no answer"
                                    )
                                citations = CitationValidator(self.runtime.index).validate(
                                    answer, tuple(all_sources)
                                )
                                duration_ms = int((time.monotonic() - started) * 1000)
                                self.runtime.chats.append_message(
                                    chat_id,
                                    prepared.request_id,
                                    "assistant",
                                    answer,
                                    completed=True,
                                    metadata={
                                        "provider": provider,
                                        "model": prepared.generation.model,
                                        "duration_ms": duration_ms,
                                        "citations": citations,
                                        "tool_rounds": 0,
                                    },
                                )
                                self.runtime.activity.emit(
                                    "provider_request_completed",
                                    chat_id=chat_id,
                                    request_id=prepared.request_id,
                                    provider=provider,
                                    model=prepared.generation.model,
                                    status="success",
                                    duration_ms=duration_ms,
                                )
                                self.runtime.activity.emit(
                                    "answer_saved",
                                    chat_id=chat_id,
                                    request_id=prepared.request_id,
                                    complete=True,
                                )
                                self._schedule_compaction(chat_id, prepared.request_id)
                                for citation in citations:
                                    yield ProviderEvent("citation", citation=citation)
                                yield event
                                return
                            else:
                                yield event
                        raise ProviderError(
                            "incomplete_stream",
                            "Provider stream ended before completion",
                            retryable=True,
                        )
                    raise
                if not calls:
                    raise ProviderError(
                        "incomplete_stream",
                        "Provider stream ended before completion",
                        retryable=True,
                    )
                if tool_rounds >= self.runtime.settings.max_tool_rounds:
                    raise ProviderError(
                        "tool_round_limit",
                        "The model reached the maximum Library retrieval rounds",
                        retryable=False,
                    )
                tool_rounds += 1
                self.runtime.activity.emit(
                    "retrieval_tool_round_started",
                    chat_id=chat_id,
                    request_id=prepared.request_id,
                    provider=provider,
                    model=prepared.generation.model,
                    round=tool_rounds,
                    call_count=len(calls),
                )
                yield ProviderEvent(
                    "status",
                    stage="retrieving",
                    label=f"Searching Library (additional round {tool_rounds})",
                )
                for call in calls:
                    try:
                        result = await asyncio.to_thread(dispatcher.dispatch, call)
                    except (ToolDispatchError, KeyError, ValueError):
                        result = {
                            "error": "The requested Library lookup is invalid or unavailable."
                        }
                        self.runtime.activity.emit(
                            "retrieval_tool_failed",
                            chat_id=chat_id,
                            request_id=prepared.request_id,
                            tool=call.name,
                            error_category="invalid_or_unavailable_source",
                        )
                    else:
                        self.runtime.activity.emit(
                            "retrieval_tool_completed",
                            chat_id=chat_id,
                            request_id=prepared.request_id,
                            tool=call.name,
                            result_count=len(result.get("sources", []))
                            if call.name == "search_library"
                            else 1,
                        )
                    exchanges.append(ToolExchange(call, result))
                    new_records = (
                        result.get("sources", [])
                        if call.name == "search_library"
                        else ([result] if result.get("available") is True else [])
                    )
                    for source in new_records:
                        chunk_id = source.get("chunk_id")
                        if not isinstance(chunk_id, str) or any(
                            item.chunk_id == chunk_id for item in all_sources
                        ):
                            continue
                        page_start = source.get("page_start", source.get("page"))
                        page_end = source.get("page_end", source.get("page"))
                        if not isinstance(page_start, int) or not isinstance(page_end, int):
                            continue
                        excerpt = SourceExcerpt(
                            chunk_id=chunk_id,
                            document_id=source["document_id"],
                            filename=source["filename"],
                            page_start=page_start,
                            page_end=page_end,
                            text=source["text"],
                            index_version=source["index_version"],
                        )
                        all_sources.append(excerpt)
                    yield ProviderEvent("retrieval", sources=tuple(new_records))
        except asyncio.CancelledError:
            await self._save_incomplete(
                chat_id, prepared, text_parts, provider, "canceled", started
            )
            raise
        except ProviderError as exc:
            await self._save_incomplete(
                chat_id, prepared, text_parts, provider, exc.category, started
            )
            raise

    async def _save_incomplete(
        self,
        chat_id: str,
        prepared: PreparedTurn,
        text_parts: list[str],
        provider: str,
        reason: str,
        started: float,
    ):
        duration_ms = int((time.monotonic() - started) * 1000)
        partial = "".join(text_parts)
        if partial:
            self.runtime.chats.append_message(
                chat_id,
                prepared.request_id,
                "assistant",
                partial,
                completed=False,
                metadata={
                    "provider": provider,
                    "model": prepared.generation.model,
                    "duration_ms": duration_ms,
                    "terminal_reason": reason,
                },
            )
        self.runtime.activity.emit(
            "provider_request_completed",
            chat_id=chat_id,
            request_id=prepared.request_id,
            provider=provider,
            model=prepared.generation.model,
            status=reason,
            duration_ms=duration_ms,
        )

    def _schedule_compaction(self, chat_id: str, request_id: str) -> None:
        compactor = getattr(self.runtime, "compactor", None)
        if compactor is None:
            return
        try:
            compactor.schedule_if_due(chat_id)
        except (RuntimeError, OSError, ValueError):
            self.runtime.activity.emit(
                "compaction_scheduling_failed",
                chat_id=chat_id,
                request_id=request_id,
                error_category="checkpoint_read_failed",
            )
