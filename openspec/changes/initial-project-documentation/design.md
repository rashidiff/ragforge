# Design

## Context

See proposal.md for motivation. The repository currently contains only agent.md, OpenSpec configuration, and workflow skills; no frontend, backend, tests, or dependency lockfiles exist. These are proposed decisions, not observations of working software. requirements-baseline.md preserves the complete source and maps all twelve source sections to capabilities and phases. Root agent.md controls any discrepancy. No runtime files are introduced in this change.

## Goals / Non-Goals

**Goals:** Define implementable module boundaries, typed contracts, ordering invariants, failure behavior, test gates, and a phased delivery sequence for the entire specified product. Keep required behavior mandatory and original optional features explicit.

**Non-Goals:** Application implementation during planning; accounts, hosted state, remote embeddings/OCR, external factual retrieval, unrestricted agent tools, and unnecessary agent frameworks. Optional OCR, reranking, additional retrieval rounds, compatible endpoints, and vault persistence must never gate core deterministic retrieval. The recommended exports are included in the proposed roadmap.

## Decisions

### D1. Runtime, stack, configuration, and source layout

Use Python 3.11+, FastAPI, Pydantic, Uvicorn; React, TypeScript, Vite, Tailwind, accessible primitives and Lucide. Production serves built static assets from FastAPI on 127.0.0.1; development permits only the explicit local Vite origin. No account/authentication UI, SQLite/Postgres, database server, Docker requirement, or cloud infrastructure. This follows the prescribed local-file architecture rather than introducing infrastructure.

Implement the exact module/file responsibilities in agent.md section 7 (preserved in the baseline): backend API routes for chats/library/settings/status; domain schemas/events; ingestion/chunking/embeddings/vector/lexical/retrieval/orchestration/context/prompt/history/logging/credential services; separate asynchronous provider adapters; frontend app/components/pages/hooks/lib/styles; Windows and POSIX scripts. Keep imports directed API -> services -> stores/adapters, with domain contracts shared across boundaries. Do not mix prompt prose into route code.

Validated non-secret settings include host/port, managed data root, upload limit (suggested 50 MB), embedding identifier/revision, chunk target/overlap (starting 500/80 tokens), OCR/languages, optional reranker, retrieval candidate/snippet/token limits, model context/output limits, timeouts, tool-round limit (maximum two), summary target (500-900 tokens), and debug opt-in. Use safe .env.example defaults; ignore environment files, generated assets, data, indexes, and secrets. Pin versions in lockfiles after OS/Python compatibility checks. If faiss-cpu is incompatible, document and test an entirely local substitute preserving index contracts; never silently use a hosted service.

Alternative: a generic chat wrapper or hosted vector service is simpler but cannot satisfy the required offline preprocessing and provenance guarantees.

### D2. Frontend architecture

App routes select Chat, Library, and Settings; sidebar owns navigation and chronological chat metadata, not canonical messages. Typed API client owns requests and error mapping. Stream-reader hook owns incremental UTF-8/SSE decoding and AbortController; per-request reducer owns stages, accumulated deltas, citations, usage, terminal state, and stale-event guards. Reload history from the backend after successful completion; do not make browser storage authoritative or store credentials there.

Components cover Sidebar, MessageList, MarkdownMessage, Composer, RequestStatus, Citation, SourceDrawer, PdfPreview, UploadProgress, and SettingsForm. Use sanitized Markdown with raw HTML disabled, code blocks, escaped filenames, focus indicators, keyboard controls, responsive sidebar, RTL-aware layout and mixed bidi isolation. Follow the detailed controls and status timelines in the chat-experience spec and source section 3. Composer preserves exact submitted text while rejecting whitespace-only input. Retry creates a new request attempt linked to the already saved user message, avoiding a duplicate user entry. Auto-scroll only while the user is at the bottom. Deleted historical sources show unavailable.

Alternative: EventSource cannot POST the required JSON body; use fetch and streamed SSE parsing instead. A fake typewriter would obscure real cancellation and timing.

### D3. Local PDF/index lifecycle

Persist originals to data/library/pdfs/<UUID>.pdf only after extension/signature/content validation, size limits, safe managed-path resolution, and readable/non-encrypted validation. SHA-256 drives duplicate detection. Manifest tracks original filename/title, size, pages, imported_at, content hash, status, warnings, index_version, error. An accepted upload returns a job; UI polls status rather than waiting for extraction in the request.

Use PyMuPDF page blocks/dict extraction, reasonable reading order, preserved table text where possible, and Unicode-safe normalization for search only; never normalize archive message text. Detect sparse scans; optional local Tesseract checks executable and language packs explicitly. Unusable scans stay warned/failed, not falsely ready. Heading/paragraph-aware chunks target 500 tokens with 80 overlap; default to page-contained chunks; retain exact ranges if spanning is necessary.

Use sentence-transformers with default intfloat/multilingual-e5-small, configured revision and normalized vectors. E5 queries use `query: ` and chunks `passage: ` or equivalent supported encode_query/encode_document paths. Batch embedding locally. Dense candidates start around 20, BM25 around 20, RRF fusion; optionally rerank 15-20 locally using a multilingual model, then select around 4-8 snippets within the model budget. Thresholds require a multilingual relevance fixture set; scores are not confidence percentages.

Persist faiss.index via write_index/read_index, UTF-8 chunks.jsonl, lexical index, and stable faiss_id/chunk_id mapping. Treat the files in agent.md as the active index layout; use temporary generation directories and a small atomic generation pointer/snapshot manifest to publish the entire related set together. Replacing each file independently is insufficient. Chunk metadata includes chunk_id, document_id, filename, page_start/end, text, sha256, position, embedding_model_version; generation metadata records source document versions and embedding configuration.

Indexing jobs serialize mutations; readers hold an immutable generation. Deletion first marks the document unavailable in the authoritative manifest, then rebuilds without it. Every retrieval and citation check filters current availability even for older generations. If deletion races an active answer, preserve request and historical citation records. Future retrieval excludes the removed document; historical references show unavailable. `agent.md` requires future exclusion and historical unavailability but does not define cancellation or mutation of an in-flight answer, so the implementation must use a consistent index snapshot for that request and must not invent a stronger cancellation contract. Publish rebuilt indexes only after validation; on failure retain known-good generation with unavailable documents filtered, or report unavailable if none is safe. An embedding-model change never queries old vectors with the new encoder.

Alternative: overwriting active binary/index metadata in place is simpler but exposes partial or mismatched generations and unreliable citations.

### D4. Provider adapters and grounded orchestration

Async adapter interface accepts a logical request (system instructions, memory, ordered tail, source blocks, current question, tool schema, output limit, cancellation) and emits normalized status/text/tool/usage/error events. Implement separate OpenAI, Anthropic, Gemini adapters; optional compatible adapter explicitly negotiates supported features. Preserve provider-specific roles, streaming frames, tool results, termination reasons, usage fields, and errors instead of assuming one wire format. Validate selected model's known/configured context window, output limit, tool support and endpoint; unknown limits require explicit safe configuration. Model dropdown can use provider discovery when supported with editable model names as fallback; do not freeze potentially obsolete model IDs in the plan.

Settings selects provider/model and tests a supplied/session/vault key using the actual provider. A successful test is not a guarantee of tool support; record a capability profile. Missing secrets, unsupported models, invalid key, 429, network outage, and timeout remain distinct safe errors. Log provider/model, start/end, status if exposed, duration, and available input/output usage or provider cost estimate; do not invent unavailable metrics. All provider calls, including compaction and connection tests, use the same credential and logging controls. Settings privacy explicitly covers remote snippet/context transfer and initial download requirements.

Request lifecycle: validate chat/body/model/budget basics -> durably append user -> redacted activity event -> load checkpoint/tail -> coreference-aware deterministic local retrieval -> optional reranking -> construct bounded request -> provider call -> actual streaming deltas/citations -> validate final references -> durably append exact final assistant -> done. Empty Library and absent evidence yield clear grounded responses without unsupported facts. If a local no-evidence assistant response is produced, persist it through the same completion path.

Map one canonical system.md prompt, a clearly labeled summary block, complete raw tail in chronological order, untrusted fenced excerpts with immutable source/name/pages, and one current question to provider roles. Keep the current user message separate from the tail in the logical request; adapters insert it once at the correct final position. Memory and earlier user assertions never count as evidence. Tool definitions remain in provider APIs/backend orchestration, not trusted PDF prose.

search_library(query, top_k, optional_document_ids) validates filters and limits; get_source_excerpt(chunk_id) returns only an available chunk in the pinned generation. Initial retrieval always works without tools. Optional tool-capable mode permits at most two additional rounds, each logged and visible. No file, shell, web, credential, or arbitrary network tool is available to the model. Validate final citations against the union of snippets actually retrieved in this request and current availability. For uncertain/conflicting evidence, identify uncertainty and cite both sides where supported. Document injection stays untrusted content.

Alternative: entire PDFs in prompts violate data minimization and budgets; model-only retrieval fails providers without tool support.

### D5. Context budgets and exact recursive compaction

Keep permanent archive and model-visible memory separate. For each chat, select completed user/final assistant records after the committed checkpoint, not progress, tool calls, partial answers, or another chat's messages. Stable archive sequence supplies ordering; UUIDs supply identity, not lexical sort. S1 = compact(empty, 1..8); S2 = compact(S1, 9..16); S3 = compact(S2, 17..24). Never repeatedly summarize all historical originals. Counter derives from committed archive/checkpoint rather than an increment that can be lost at crash.

Compaction obtains a per-chat lock, snapshots checkpoint revision and next batch of eight, calls the configured LLM using prompts/compaction.md, validates structured summary and token bound, then compare-and-swaps an atomic state snapshot. Persist summary, last_compacted_message_id, compacted_message_count, prompt_version, summary_revision, timestamps. Failure leaves checkpoint and tail intact and logs safe retry; repeated success cannot consume the same batch. Commit completed-message count, not count of API requests.

Structured summary sections cover entities/document selections, enduring facts with uncertainty, user preferences, decisions/constraints, unresolved questions, contradictions, and source pointers. Strip credentials from compaction input/output; this does not modify the canonical archive. Source pointers never replace retrieval. Target 500-900 tokens, configurable. Record time and available usage.

If saving the current user reaches eight, defer compaction involving that current user until after the answering turn; answer with the full eligible tail and exactly one current question if it fits. Before each call reserve output budget and safety margin; budget covers system, memory, tail, source text, current question, tool definitions and tool results. Reduce bounded retrieval, recursively rewrite eligible older memory, and emergency-compact older completed messages (including a smaller batch when necessary), preserving recent/current intent. Emergency checkpoint counts record actual consumed messages; the next regular batch is the next eight uncompacted messages. Never consume the active question merely to hide it. If safe compaction fails and input cannot fit, show a retryable context error, retain raw history, and do not silently truncate the question.

Alternative: fixed eight-message compaction alone does not bound long messages; a summary that overwrites raw history violates auditability.

### D6. Canonical records, logging, and crash recovery

The two primary canonical files are data/chat_history.jsonl (all chats) and data/system.log.jsonl (operational activity). Supporting snapshots/PDFs/indexes are separate required local files, not a database. history_store serializes append under one writer lock, writes one UTF-8 JSON object plus newline, flushes and fsyncs before acknowledging persistence. Failed persistence prevents provider generation or a false saved/done status. Stable event/message/request IDs plus sequence prevent duplicates on retry. Redacted operational logging is a separate append with its own lock and durability policy. Surface log-write failures with a clear degraded/error state and recovery guidance; do not claim a successful durable operation when its required log record could not be written. Provider cancellation or fail-closed policy for logger outages is not specified by the source requirements and is left to a separately justified implementation decision.

At startup validate JSONL sequentially. Retain all valid records; quarantine an incomplete trailing fragment before safely repairing only that suffix under lock. Mid-file corruption requires explicit recovery from backup and a visible error; never silently discard the remaining archive. Rebuild message indexes/counters from canonical records. Snapshot files use temporary write, flush/fsync, atomic rename and recoverable previous copies; exercise Windows and POSIX behavior. A single backend process and bounded concurrent jobs simplify file locking; prevent a second writer instance on the same data root.

User is persisted before provider work. Successful assistant is persisted once with exact final text and completed:true. Canceled/failed output can be appended with completed:false and terminal reason; it never counts for compaction or future model tail. On crash, persisted user without completed assistant remains visible as interrupted; no fake completion is invented. Retrying links a new request_id to the prior user_message_id. A provider text stream is provisional until valid completion and durable append.

Chat deletion confirms, tombstones metadata first, cancels active work, excludes chat from UI/model access, and explicitly garbage-collects only that chat's records through a locked atomic archive rewrite. This is the sole intentional exception to normal append-only history. Restore/GC use backups and verify other chats' byte-equivalent decoded content. Backups may retain deleted content; disclose this locally. PDF deletion leaves raw history and historical citation text unchanged, with availability separate.

### D7. Security and local storage

Keep secrets in session memory by default; explicit keyring opt-in alone enables persistence. Keyring unavailability is an error, not permission for plaintext fallback. Read settings returns has_key and persistence mode, never api_key. The browser only temporarily holds the entered key until submission and clears the field; no browser/localStorage persistence. Provider key updates/removal never echo secret values. Never log authorization headers, request headers with secrets, keys, or secret-bearing full prompts. Redact likely credentials in activity messages; warn if user message contains a likely key because raw history intentionally remains verbatim. Full retrieved text logging requires explicit local debug and still applies redaction.

Restrict origins/Host headers to configured local origins and loopback hosts; reject cross-origin mutation, resolve managed paths securely, validate UUID lookups, escape/sanitize all rendered text, and bound upload size, jobs, timeouts, and request concurrency. One active generation per chat returns a conflict for overlapping submissions; other chats may proceed within configured limits. Treat PDF instructions as data at every stage. Do not expose credentials or privileged tools to providers. No analytics/telemetry without explicit opt-in. Local files are not encrypted by default: disclose OS-user access and recommend OS disk/account controls without claiming app authentication.

Alternative: plaintext config or browser storage for keys is convenient but violates the explicit secret-storage boundary.

### D8. API and data contracts

Pydantic domain schemas generate OpenAPI and TypeScript contracts; CI checks generated-type drift. All UUID fields are strings, timestamps timezone-qualified ISO-8601, text UTF-8, pages 1-based, byte sizes nonnegative. Non-stream errors use {error:{code,message,retryable,request_id?,details?}} with sanitized details. Unknown/deleted IDs return 404, malformed inputs 422, unsupported content 415, oversized input 413, duplicate/concurrency/rebuild conflicts 409, missing/invalid provider credentials a safe categorized 400, upstream failures 502/503 and timeout 504. Local validation occurs before user append; errors after durable user save leave that saved user visible. No error returns secrets or internal paths.

| Endpoint | Input | Successful output |
|---|---|---|
| GET /api/health | none | 200 {status,version,storage_ready,index_ready,warnings} |
| GET /api/chats | none | 200 {chats:Chat[]} chronological |
| POST /api/chats | {title?:string} | 201 Chat with safe automatic initial title |
| PATCH /api/chats/{chat_id} | {title:string} | 200 Chat |
| DELETE /api/chats/{chat_id} | confirmed UI action | 204 after durable tombstone; GC status logged |
| GET /api/chats/{chat_id}/messages | none | 200 {messages:Message[]} full raw messages, including explicitly incomplete records |
| POST /api/chats/{chat_id}/messages/stream | {content:string,client_message_id:UUID} or {retry_of_request_id:UUID} exclusively | 200 text/event-stream after validation; server creates request_id |
| GET /api/library | none | 200 {documents:Document[]} |
| POST /api/library/upload | multipart file:PDF | 202 {document:Document,job_id}; duplicate 409 with existing document_id |
| DELETE /api/library/{document_id} | none | 202 {job_id,status:deleting}; document immediately unavailable |
| POST /api/library/{document_id}/reindex | none | 202 Job |
| GET /api/library/{document_id}/pdf | managed ID | 200 application/pdf; frontend uses #page=N fragment |
| GET /api/index/status | optional job_id query | 200 {index_version,jobs:Job[],ready,warnings} |
| POST /api/index/rebuild | none | 202 Job |
| GET /api/settings | none | 200 public Settings with has_key only |
| PUT /api/settings | validated patch, optional write-only api_key, clear_key, persist_key | 200 public Settings; embedding change marks rebuild required |
| POST /api/settings/test-connection | optional write-only key/provider/model candidate | 200 {ok,provider,model,capabilities}; no echo of key |
| GET /api/chats/{chat_id}/export | format=markdown or json | 200 safe attachment for live chat |
| GET /api/history/backup | none | 200 coherent locked/snapshotted JSONL attachment, with sensitive-history warning |

Settings includes provider, model, optional endpoint, capability/limit configuration, embedding model, OCR, retrieval settings, privacy/storage summary and key persistence mode. keyring persistence is explicit false by default; api_key and clear_key are mutually exclusive. Compatible endpoints are user configuration, never model-selected URLs.

Core records:

- Chat: {chat_id,title,created_at,updated_at,deleted_at?}.
- Message: {event_id,chat_id,message_id,role:user|assistant,content,created_at,completed,request_id,metadata}. Metadata includes sequence, attempt linkage, terminal reason if incomplete, citation pointers and provider usage as applicable. Completed content is never regenerated from Markdown DOM.
- Document: {document_id,original_name,title,sha256,size_bytes,page_count,imported_at,status,warnings,index_version,error?}; states validating/extracting/ocr/chunking/embedding/indexing/ready/failed/deleting.
- Chunk: {chunk_id,document_id,filename,page_start,page_end,text,sha256,position,embedding_model_version}; separate stable faiss_id mapping.
- Source: {chunk_id,document_id,filename,page,page_start,page_end,score,index_version,available}; score is retrieval-specific, not calibrated confidence.
- Job: {job_id,kind,document_id?,stage,processed,total?,started_at,finished_at?,error?}; no fake percentage if total unknown.
- CompactionState: {chat_id,summary,last_compacted_message_id,compacted_message_count,prompt_version,summary_revision,created_at,updated_at}.
- Activity: {timestamp,severity,event_type,chat_id?,request_id?,document_id?,duration_ms?,query_redacted?,sources?,provider?,model?,status_code?,usage?,cost_estimate?,error_category?,details?}. Never serialize unfiltered SDK objects.

SSE frames use event name then JSON data and a blank line. All events carry request_id and monotonic per-request sequence. status carries stage/label; retrieval carries sources and round; token carries delta; citation carries a validated Source and display marker; usage carries available input/output/total token fields; done carries message_id and complete:true; error carries safe code/message/retryable and complete:false. Heartbeat comments keep waits alive and never create messages or counts. Exactly one terminal done or error when connection remains writable; disconnected streams may have no terminal frame. AbortController cancellation propagates to backend task and provider; backend finalization records incomplete output. No done precedes durable assistant save. Frontend handles partial lines, CRLF, multiline data, multiple frames per read, and UTF-8 code points spanning reads.

Alternative: hand-copied unverified frontend types drift; generated contracts and a CI drift check make compatibility reviewable.

### D9. Verification and independently deliverable phases

Use pytest/FastAPI tests; Vitest/React Testing Library; Playwright real browser smoke. Each phase ships its own focused tests and documentation. Test doubles cover malformed provider frames, errors, retries, and failure injection; at least one real provider plus real local indexing is mandatory for release. Never label mocked streaming as true end-to-end evidence. Consult current primary reference documentation from source section 12 during implementation before pinning SDK/API behavior; this planning change makes no externally verified compatibility claim.

| Phase | Dependencies | Runnable deliverable and acceptance gate |
|---|---|---|
| 1 Local foundation and durable chats | none | Shell, typed API, local launch, canonical history/log primitives, prompt loading; source acceptance 1 and foundational 7/11 |
| 2 PDF Library and local search | 1 | Validated upload, progress, page preview, extraction/chunking/local hybrid persistence, restart/deletion; acceptance 2 retrieval portion, 4,9 |
| 3 Providers and Settings | 1 | All three required adapters and safe credentials/test connection/capabilities; acceptance 5, adapter protocol checks |
| 4 Grounded streaming conversation | 2,3 | Orchestration, live deltas, citations, stop/retry, absent/conflicting evidence; acceptance 2,3,6,8,10 |
| 5 Recursive memory and budget recovery | 4 and phase-1 stores | Exact recursion/checkpoints, emergency budgets, restart/failure recovery; acceptance 7,8 |
| 6 Optional enhancements and index hardening | 2,4,5 | OCR/reranking/tools/compatible endpoint when enabled, tested fallback and races; acceptance 4,8,9,10 |
| 7 Interaction polish and exports | 4,5; optional UI integrates 6 if present | Responsive/RTL/accessibility, themes, copy/scroll, safe export/backup; acceptance 11 and export checks |
| 8 Release integration and packaging | 1-7 required baseline and explicitly supported optional features | Platform launch matrix, all acceptance evidence, live smoke, locks/README/test report; acceptance 1-12 |

Each slice is independently implementable once its declared dependencies land. Phase 3 can follow phase 1 without phase 2. Phase 7 can follow phase 5 while optional phase 6 work is pending. Phase-1 durable stores are foundational: postponing them until memory integration would violate persist-before-generation in phase 4. These dependencies refine the five high-level source slices without removing any of them.

Detailed verification fixtures include normal multilingual/table PDFs, contradictory and unrelated documents, identifiers/coreference queries, duplicates, malformed/encrypted/oversized/scanned files, injection instructions, unavailable OCR packs, deleted sources during stream, broken indexes, partial JSONL, failed fsync/rename, canceled upstream, split UTF-8/SSE frames, invalid citations, unsupported models, missing keys, invalid keys, 429, timeout, outage, and compaction 8/16/24 plus independent chats. Measure indexing/retrieval/API latency and context sizes on declared fixtures; no unsupported numeric latency SLA is invented. Responsiveness requires asynchronous/offloaded CPU work, bounded queues and true progress, not a guessed performance promise.

## Risks / Trade-offs

- [Multilingual extraction and OCR reading order vary] -> Preserve page provenance, exercise Persian/French/English fixtures, document limitations and missing packs.
- [Local ML packages differ by OS/Python] -> Compatibility matrix and locked tested versions; explicit tested local vector alternative when necessary.
- [LLM summaries can lose constraints or hallucinate] -> Structured validation, bounded recursion, source-pointer-only memory, golden tests, retain raw archive, and retrieval on every document question.
- [Provider cancellation/usage/tools vary] -> Capability profiles, adapter-specific tests and graceful explicit unsupported states.
- [Append-only history grows indefinitely and may include pasted secrets] -> Disclose local disk/privacy costs, support backups and explicit chat deletion; never auto-truncate.
- [Atomic multi-file updates and deletion races] -> Generation publication, availability checks, write locks, and crash-injection tests; retain citation availability separately from historical citation content. Do not require forced stream cancellation on deletion without further product decision.
- [Optional feature scope] -> Feature flags and explicit capability reporting; mandatory baseline never reports an untested optional feature as working.

## Migration Plan

There is no existing application data to migrate. Planning changes remain in the change directory for review; implementation requires a new explicit apply request. Later implementation creates data directories on first launch, validates local schema versions, backs up before state-format migrations, and never migrates by rewriting canonical message content. Failed index migration rebuilds from original PDFs; raw-history corruption requires explicit backup recovery. Rollback restores compatible snapshot/index generations and code/locks without deleting original PDFs or canonical logs. Schema downgrade refuses unsafe writes when incompatible rather than guessing.

## Open Questions

None blocking planning. Concrete dependency patch versions, live model IDs, and fixture-specific retrieval thresholds will be selected and recorded during the compatibility/evaluation tasks; the architecture and observable contracts above do not depend on guessing them now.


### D10. Contract and requirement traceability

The detailed source-to-specification-to-scenario-to-task matrix is maintained in `requirements-baseline.md`, keyed by stable capability requirement IDs (e.g. `GG-1`, `API-2`, `PL-6`). Treat that file as the review index, not an independent source of product policy; `agent.md` remains authoritative. Each implementation task in `tasks.md` names the requirement IDs it delivers and the observable evidence used to accept it. Each of the twelve release criteria names the relevant scenario IDs or implementation evidence. This avoids a task being marked done while a behavior has no owner or acceptance evidence.

The API uses JSON for non-streaming successes and errors. The shared error envelope is `{error:{code,message,retryable,request_id?,details?}}`; details contain field names and safe remediation only. Chosen status mapping: malformed JSON/field constraints 422; unsupported media/PDF signature 415; configured byte limit exceeded 413; unknown or deleted resource 404; duplicate upload, active per-chat generation, or conflicting index mutation 409; provider credentials rejected 401; provider throttling 429; upstream timeout 504; upstream unavailable/protocol failure 502 or 503; local persistence failure 500 with a safe retry/recovery message. Stream setup validation uses the same HTTP statuses before response headers; after headers, terminal `error` event carries the corresponding code and `complete:false`. No key, authorization header, prompt containing a key, internal path, or raw stack trace is returned. These categories are API-level behavior; logs retain sanitized correlation and error category.

Route contract matrix (request/response fields are typed; IDs and timestamps follow the data structures below):

| Route | Request | Success contract | Key errors |
|---|---|---|---|
| `GET /api/health` | none | 200 `Health{status,version,storage_ready,index_ready,warnings}` | 503 if required storage cannot be read |
| `GET /api/chats` | none | 200 `{chats: Chat[]}` chronological | 500 safe persistence read error |
| `POST /api/chats` | `{title?: string}` | 201 `Chat` | 422 invalid title; 500 persistence failure |
| `PATCH /api/chats/{chat_id}` | `{title: string}` | 200 `Chat` | 404 unknown/deleted; 422 invalid title |
| `DELETE /api/chats/{chat_id}` | confirmed action is UI requirement | 204 after durable tombstone; cleanup state logged | 404 unknown/deleted; 500 if tombstone cannot persist |
| `GET /api/chats/{chat_id}/messages` | none | 200 `{messages: Message[]}` complete chat history, including explicitly incomplete attempts | 404 unknown/deleted |
| `POST /api/chats/{chat_id}/messages/stream` | `{content,client_message_id}` OR `{retry_of_request_id}`, exclusive | 200 `text/event-stream`; persist user before provider work; `done` only after exact assistant append | 404 chat; 409 overlapping generation; 422 empty/invalid or both retry and content; 401 rejected provider credentials; 429/502/503/504 provider errors; terminal stream error after headers |
| `GET /api/library` | none | 200 `{documents: Document[]}` | 500 safe manifest read error |
| `POST /api/library/upload` | multipart `file` | 202 `{document: Document,job_id}` after accepted validation | 413 size; 415 type/signature; 409 duplicate with existing ID; 422 encrypted/unreadable |
| `DELETE /api/library/{document_id}` | none | 202 `{job_id,status: deleting}`; immediately excluded from future retrieval | 404 unknown ID; 409 conflicting mutation |
| `POST /api/library/{document_id}/reindex` | none | 202 `Job` | 404 unknown ID; 409 concurrent mutation |
| `GET /api/library/{document_id}/pdf` | UUID path; page fragment is client-side | 200 `application/pdf` of managed source only | 404 unknown/deleted; 416 invalid range if byte ranges are supported |
| `GET /api/index/status` | optional `job_id` | 200 `{index_version,jobs,ready,warnings}` | 404 unknown job |
| `POST /api/index/rebuild` | none | 202 `Job` | 409 rebuild already running; 503 no safe readable index during rebuild failure |
| `GET /api/settings` | none | 200 public settings and `has_key`; never key value | 500 safe config read error |
| `PUT /api/settings` | validated settings plus write-only `api_key` OR `clear_key`, optional `persist_key` | 200 public settings; embedding change sets `rebuild_required` | 422 invalid/mutually exclusive options; 500 safe persistence/keyring error |
| `POST /api/settings/test-connection` | optional candidate provider/model and write-only key | 200 `{ok,provider,model,capabilities}` or categorized safe error | 401 invalid key; 422 unsupported options; 429/502/503/504 upstream failures |
| `GET /api/chats/{chat_id}/export?format=markdown|json` | format | 200 safe attachment | 404 unknown chat; 422 unsupported format |
| `GET /api/history/backup` | none | 200 coherent archive attachment under locked/snapshotted read | 500 safe read error |

A duplicate upload reports the existing document rather than accepting a second ingestion. A configured embedding change invalidates readiness until a complete validated generation has been published; no mixed model/index generation is queryable. `ready=true` means the active index and lexical metadata share a validated generation and at least one selected active document has completed extraction and indexing, or the Library is successfully initialized empty (`ready=true`, zero active documents, explicit empty warning). Each document's own status is the authority for whether it can be retrieved. Progress `total` may be absent where work cannot be predicted; never fabricate percentages.

The table does not invent requirements beyond the source except safe contract details needed to make validation and acceptance concrete. Where concurrency during a deletion is unspecified, the pinned generation governs the already-running request; later requests must exclude the removed document, and citation availability reflects current state.

### D11. GitHub-hosted CI

`.github/workflows/ci.yml` is the automated execution boundary for push and pull-request checks. Separate Ubuntu jobs provision Python 3.11 and Node.js 22, cache pip/npm downloads, enforce bounded timeouts, and fail the workflow on any failed command. Backend CI installs the `dev` and lightweight `ci` extras (PDF parsing, NumPy, FAISS, and BM25; no sentence-transformer weights), runs all pytest cases, Ruff lint/format checks, and mypy. Frontend CI installs npm packages, runs Vitest, mocked Chromium Playwright integration, ESLint, Prettier check mode, TypeScript type checking, and the Vite production build. Tests use temporary directories and deterministic mock adapters/transports; no provider secret is configured. The real-provider/browser acceptance flow remains a separate release gate. Workflow authoring is not evidence of a successful CI run.
