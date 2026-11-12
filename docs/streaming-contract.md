# Chat stream and citation contract

`POST /api/chats/{chat_id}/messages/stream` accepts a JSON `MessageSubmission` and
returns `text/event-stream`. A new turn contains `content` and
`client_message_id`; a retry contains only `retry_of_request_id`. Empty content,
malformed IDs, a missing chat, and a conflicting active request fail before stream
headers are sent. The user record is durably appended before retrieval or provider
work starts.

## Frame format

Each event frame has one `event:` line and a JSON `data:` line, terminated by a
blank line. UTF-8 is used; heartbeat comments (`: heartbeat`) carry no data and
must not be treated as application events. The frontend incrementally decodes
UTF-8, tolerates CRLF, buffers incomplete frames and joins multiple `data:` lines.

| Event | Payload | Meaning |
|---|---|---|
| `status` | `{stage, label, request_id?}` | Actual request stage, such as validation, retrieval, compaction, provider call, streaming, or save |
| `retrieval` | `{request_id, sources[]}` | Sources selected for the request, with chunk/document IDs, filename, page range, and optional ranking score |
| `token` | `{request_id, delta}` | Exact upstream text delta, or the deterministic empty-library/insufficient-evidence answer |
| `citation` | `{request_id, chunk_id, document_id, filename, page_start, page_end, url}` | Citation validated against sources for this request and current document availability |
| `usage` | `{request_id, input_tokens?, output_tokens?, total_tokens?}` | Provider-reported usage only; absent values are not estimated |
| `done` | `{request_id, message_id, complete: true, duration_ms}` | Emitted only after the exact final assistant answer is durably saved |
| `error` | `{error: {code, message, retryable, request_id?, details?}}` | Terminal failure after headers; it never represents a completed answer |

The event order is lifecycle-driven: request validation and initial retrieval statuses
precede source events; provider and streaming statuses appear only when those stages
occur. Optional retrieval rounds may add further retrieval/status events. No synthetic
typing delay or private reasoning event is part of the contract. Events after a
terminal `done` or `error` are invalid.

## Errors and termination

Validation, missing/deleted chats, and an already-running request use the shared JSON
error envelope before streaming starts. Once headers are sent, provider, retrieval,
budget, persistence, and unexpected errors use an `error` event. Common categories
include `rate_limited`, `timeout`, `network_error`, `unsupported_tools`,
`index_unavailable`, `context_budget_exceeded`, `generation_failed`, and
`incomplete_stream`; the backend maps these to safe messages and retry guidance.
Raw upstream bodies, credentials, internal paths, and stack traces are not returned.

Aborting the browser request or disconnecting the client cancels the local request
and upstream provider operation where supported. A partial assistant response remains
explicitly incomplete in raw history. Retry creates a new request attempt linked to
the already-saved user message; it does not append a duplicate user message. A
missing `done` frame is treated by the frontend as an incomplete stream.

## Citation behavior

Only sources retrieved for this request and still available in the active Library can
be cited. Each citation opens its managed PDF at the recorded one-based page. The
source drawer loads the excerpt using the document/chunk IDs; unavailable/deleted
sources remain historical text and are not rewritten. No citation is inferred from
memory or from model text alone.

## Verification status

The backend and frontend stream-parser tests are authored, including cancellation,
split UTF-8, CRLF, heartbeat, missing terminal events, and safe provider errors. They
have not been run. No real local-PDF/live-provider browser smoke or source acceptance
result is claimed; task 4.9 and V4.9 remain open until that evidence is recorded.
