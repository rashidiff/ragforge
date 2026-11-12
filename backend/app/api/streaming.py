"""POST JSON + actual provider deltas using a small UTF-8 SSE event envelope."""
import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.domain.schemas import (DoneEvent, ErrorDetail, ErrorResponse, MessageSubmission,
    RetrievalEvent, RetrievedSource, StreamCitationEvent, StreamStatus, TokenEvent, UsageEvent)
from app.llm.base import ProviderError
from app.services.chat_orchestrator import ChatOrchestrator, RetryNotFoundError
from app.services.index_manager import IndexUnavailableError
from app.services.generation_registry import GenerationConflictError

router = APIRouter(prefix="/api/chats", tags=["chat-stream"])


def _frame(event: str, data) -> bytes:
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/{chat_id}/messages/stream")
async def stream_message(chat_id: UUID, body: MessageSubmission, request: Request):
    runtime = request.app.state.runtime
    runtime.chats.get(str(chat_id))
    lease = runtime.generations.acquire(str(chat_id))

    async def events():
        started = time.monotonic()
        cancellation = lease.cancellation
        prepared = None
        prepare_task = None
        yield _frame("status", StreamStatus(stage="validating", label="Validating request"))
        yield _frame("status", StreamStatus(stage="retrieving", label="Searching Library"))
        try:
            orchestrator = ChatOrchestrator(runtime, request.app.state.prompts)
            prepare_task = asyncio.create_task(run_in_threadpool(orchestrator.prepare, str(chat_id), body))
            while not prepare_task.done():
                done, _ = await asyncio.wait({prepare_task}, timeout=15)
                if done:
                    break
                if await request.is_disconnected():
                    prepare_task.cancel()
                    return
                yield b": heartbeat\n\n"
            prepared = prepare_task.result()
            if prepared.generation.sources:
                compaction_updates = asyncio.Queue()
                budget_task = asyncio.create_task(orchestrator.fit_context(prepared,
                    on_compaction=lambda count: compaction_updates.put_nowait(count)))
                while not budget_task.done():
                    update_task = asyncio.create_task(compaction_updates.get())
                    done, _ = await asyncio.wait({budget_task, update_task}, timeout=15,
                        return_when=asyncio.FIRST_COMPLETED)
                    if update_task in done:
                        yield _frame("status", StreamStatus(stage="compacting",
                            label=f"Compacting {update_task.result()} older messages to fit context",
                            request_id=prepared.request_id))
                        continue
                    update_task.cancel()
                    await asyncio.gather(update_task, return_exceptions=True)
                    if budget_task in done:
                        break
                    if await request.is_disconnected():
                        budget_task.cancel()
                        await asyncio.gather(budget_task, return_exceptions=True)
                        return
                    yield b": heartbeat\n\n"
                prepared = budget_task.result()
            request_id = prepared.request_id
            sources = [RetrievedSource(chunk_id=source.chunk_id, document_id=source.document_id,
                        page=source.page_start, page_end=source.page_end,
                        filename=source.filename,
                        score=next((item.get("score") for item in prepared.retrieval_sources
                                    if item.get("chunk_id") == source.chunk_id), None))
                       for source in prepared.generation.sources]
            yield _frame("retrieval", RetrievalEvent(request_id=request_id, sources=sources))
            if prepared.generation.sources:
                values = runtime.app_settings.read()
                yield _frame("status", StreamStatus(stage="calling_provider",
                    label=f"Calling {values['provider']} / {prepared.generation.model}",
                    request_id=request_id))
            else:
                yield _frame("status", StreamStatus(stage="grounding",
                    label="Preparing a response limited to available PDF evidence",
                    request_id=request_id))

            reply = orchestrator.respond(prepared, cancellation).__aiter__()
            pending = None
            streaming_status_sent = False
            while True:
                if pending is None:
                    pending = asyncio.create_task(anext(reply))
                done, _ = await asyncio.wait({pending}, timeout=15)
                if not done:
                    if await request.is_disconnected():
                        cancellation.cancel()
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
                        return
                    yield b": heartbeat\n\n"
                    continue
                try:
                    event = pending.result()
                except StopAsyncIteration:
                    break
                pending = None
                if event.kind == "text":
                    if prepared.generation.sources and not streaming_status_sent:
                        yield _frame("status", StreamStatus(stage="streaming",
                            label="Streaming answer", request_id=request_id))
                        streaming_status_sent = True
                    yield _frame("token", TokenEvent(request_id=request_id, delta=event.delta))
                elif event.kind == "citation":
                    yield _frame("citation", StreamCitationEvent(request_id=request_id, **event.citation))
                elif event.kind == "usage":
                    yield _frame("usage", UsageEvent(request_id=request_id,
                        input_tokens=event.usage.input_tokens,
                        output_tokens=event.usage.output_tokens,
                        total_tokens=event.usage.total_tokens))
                elif event.kind == "status":
                    yield _frame("status", StreamStatus(stage=event.stage, label=event.label,
                        request_id=request_id))
                elif event.kind == "retrieval":
                    yielded_sources = []
                    for source in event.sources:
                        page = source.get("page", source.get("page_start"))
                        page_end = source.get("page_end", page)
                        if page is None:
                            continue
                        yielded_sources.append(RetrievedSource(chunk_id=source["chunk_id"],
                            document_id=source["document_id"], page=page, page_end=page_end,
                            filename=source["filename"], score=source.get("score")))
                    yield _frame("retrieval", RetrievalEvent(request_id=request_id,
                        sources=yielded_sources))
                elif event.kind == "done":
                    assistant = next((record for record in reversed(runtime.history.records(str(chat_id)))
                        if record.get("request_id") == request_id and record.get("role") == "assistant"), None)
                    if assistant is None or assistant.get("completed") is not True:
                        raise ProviderError("incomplete_response", "The answer was not saved as complete")
                    yield _frame("status", StreamStatus(stage="saved", label="Saved", request_id=request_id))
                    yield _frame("done", DoneEvent(request_id=request_id,
                        message_id=assistant["message_id"], complete=True,
                        duration_ms=int((time.monotonic() - started) * 1000)))
                    return
            raise ProviderError("incomplete_stream", "The response ended before completion", retryable=True)
        except asyncio.CancelledError:
            cancellation.cancel()
            raise
        except RetryNotFoundError:
            yield _frame("error", ErrorResponse(error=ErrorDetail(code="retry_not_found",
                message="The previous request is unavailable for retry.", retryable=False,
                request_id=prepared.request_id if prepared else None)))
        except ProviderError as exc:
            yield _frame("error", ErrorResponse(error=ErrorDetail(code=exc.category,
                message=str(exc), retryable=exc.retryable,
                request_id=prepared.request_id if prepared else None)))
        except IndexUnavailableError as exc:
            yield _frame("error", ErrorResponse(error=ErrorDetail(code="index_unavailable",
                message=str(exc), retryable=True,
                request_id=prepared.request_id if prepared else None)))
        except Exception:
            yield _frame("error", ErrorResponse(error=ErrorDetail(code="generation_failed",
                message="The request could not be completed. Check local status and retry.",
                retryable=True, request_id=prepared.request_id if prepared else None)))
        finally:
            if prepare_task is not None and not prepare_task.done():
                prepare_task.cancel()
                await asyncio.gather(prepare_task, return_exceptions=True)
            if "budget_task" in locals() and not budget_task.done():
                budget_task.cancel()
                await asyncio.gather(budget_task, return_exceptions=True)
            if "pending" in locals() and pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if "reply" in locals():
                await reply.aclose()
            cancellation.cancel()
            runtime.generations.release(lease)

    return StreamingResponse(events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        background=BackgroundTask(runtime.generations.release, lease))
