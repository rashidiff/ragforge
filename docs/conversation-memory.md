# Conversation memory and context recovery

The application keeps the canonical conversation archive separate from derived,
model-visible memory. `data/chat_history.jsonl` retains completed user and assistant
messages verbatim in chronological append order. Compaction writes only to
`data/state/compactions.json`; it never edits the archive. Explicit chat deletion is
the only operation that removes that chat's archive records.

## Regular recursion

Each chat has an independent checkpoint. A regular batch contains the next eight
uncompacted, complete user or finalized assistant messages. Incomplete assistant
output, provider deltas, status events and tool activity do not count. The recursive
sequence is `S1 = compact(empty, 1..8)`, `S2 = compact(S1, 9..16)`, and so on. Each
provider call receives the previous cumulative summary and only the selected new
batch, in archive order. It does not receive the entire old transcript again.

The eighth message can be the current user's saved question. To avoid delaying or
duplicating that turn, regular scheduling happens after its assistant response is
completed. A failed or canceled response remains incomplete and is not compacted as
an assistant answer. A retry is a new request attempt linked to the existing user
message; it does not append a duplicate question.

Compaction uses the editable UTF-8 `prompts/compaction.md`. The result must contain
the seven required headings, stay within the configured summary target, and have
likely credentials redacted before persistence. Summaries preserve entities,
document selections, facts with uncertainty, preferences, decisions, constraints,
unresolved questions, contradictions and source pointers. A pointer is never PDF
evidence: factual answers still retrieve available PDF passages. Activity logs record
the request ID, provider/model, selected batch boundaries, outcome, elapsed time and
provider usage when supplied; they do not record the prompt or summary text.

## Checkpoints and recovery

After a provider result is structurally validated, one atomic checkpoint update
stores the summary, final consumed message ID, cumulative consumed-message count,
prompt hash/version, summary revision, timestamps and available usage. A revision
check prevents a stale response from overwriting a newer checkpoint. If a provider
call, validation, cancellation or state write fails, the previous checkpoint stays
authoritative and the raw tail remains available. Repeating a failed attempt selects
the same uncompacted boundary; a successful commit advances it once.

On process restart, the raw archive and last committed checkpoint are read again.
No in-flight or uncommitted summary is treated as saved. Pending counts are rebuilt
from completed canonical messages after the checkpoint. The in-memory progress
state returns to idle after restart; the next completed answer schedules regular
work again when at least eight messages are pending. The compaction status endpoint
reports active-process failure details without exposing summary contents.

## Context budget and emergency batches

Before a provider request, the context planner accounts for system instructions,
summary, post-checkpoint tail, source text and metadata, the current question, tool
results/definitions when enabled, the selected model's configured context window,
and the requested output reserve. It adds a safety margin. A locally available
OpenAI tokenizer is used when present; otherwise UTF-8 byte length is the
conservative estimate. Retrieved snippets are reduced first while retaining at
least one relevant source. The summary target is bounded to 500–900 tokens.

If the request still exceeds its input budget, the planner may emergency-compact
the oldest eligible uncompacted messages in batches smaller than eight. It keeps the
newest two completed raw messages and the current question separate and unchanged.
The checkpoint records the actual smaller batch, so the next regular batch starts
at the next unconsumed archive message. Emergency compaction also observes the
selected model's request budget; if even one old message cannot be safely compacted,
the request fails clearly. If the current question and canonical system instructions
alone do not fit, no remote compaction is attempted. Nothing is silently truncated,
and an unfit question receives a retryable context-budget error. Source pruning,
summary rewriting and emergency compaction never rewrite the raw archive.

## Status and retry

`GET /api/chats/{chat_id}/compaction` reports idle, queued, running, completed or
failed state, checkpoint and pending counts, correlation ID, duration, available
usage, and a safe error category. The chat view polls while work is queued/running.
When an active-process compaction fails, the view offers a retry through
`POST /api/chats/{chat_id}/compaction/retry`. Retry is accepted only when a failed
eligible batch exists. A failed summary is never displayed as committed memory.

The summary is a convenience for bounded context, not a replacement for history.
Users can inspect the complete messages through chat history, and repeated
compaction leaves their decoded message text and order unchanged.
