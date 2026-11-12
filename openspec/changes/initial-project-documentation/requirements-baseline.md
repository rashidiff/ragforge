# Requirements baseline and traceability

This is the complete source snapshot of root `agent.md` at planning time. Root `agent.md` remains the single source of truth. All MUST/required constraints remain mandatory; optional features and suggested numerical defaults retain their original status. A reference URL is guidance, not evidence that an integration has been tested. This snapshot avoids losing details while the capability specifications express observable contracts. No behavior below is implemented by this change.

| Source requirement | Capability | Acceptance scenario | Implementation phase/task | Design |
|---|---|---|---|---|
| Preamble multilingual Unicode and answer language | chat-experience | CX-4 | 7.1, 7.5 | D2,D9 |
| 1.1 PDFs are sole factual authority; no web; uncertainty/no fabricated citations | grounded-generation | GG-1, GG-5 | 4.1-4.4, 8.3 | D4,D9 |
| 1.2 local PDFs/processing and explicit remote snippet/context boundary | privacy-and-recovery, pdf-library | PR-1, PL-5 | 2.5-2.9, 3.7, 8.3 | D3,D4,D7 |
| 1.3 single-user loopback/local files/no cloud database or Docker | local-runtime | LR-1 | 1.1,1.8,1.9,8.4-8.5 | D1,D7,D9 |
| 1.4 exact durable raw history and deletion exception | conversation-memory, privacy-and-recovery | CM-1, PR-4, PR-6 | 1.4,1.6,5.1-5.7,7.3 | D5,D6 |
| 1.5 separate durable structured operational logging/redaction | privacy-and-recovery | PR-3, PR-4 | 1.5,3.7,4.1,5.6 | D6,D7 |
| 1.6 per-chat recursive compaction every eight complete messages | conversation-memory | CM-2, CM-3 | 5.1-5.4 | D5,D6 |
| 1.7 actual streaming and honest statuses | chat-experience, local-api | CX-6, API-4 | 4.5-4.7 | D2,D4,D8 |
| 1.8 separate editable/versioned prompts | local-runtime | LR-2 | 1.7,5.2 | D1,D5 |
| 1.9 platform launch, tests, example config, no mocked success | local-runtime, release-acceptance | LR-4, RA-1-4 | 1.2,1.9,8.1-8.5 | D1,D9 |
| 2.1 stack choices and alternatives | local-runtime | LR-3, LR-4 | 1.1-1.3,2.5-2.7,8.4 | D1,D3 |
| 2.2 FAISS fallback, pinned versions, configurable E5 rebuild/prefix/normalization | pdf-library, local-runtime | PL-4, LR-3 | 1.2,2.5-2.7,6.6,8.4 | D1,D3 |
| 3 chats, Library UI/metadata/lifecycle/preview | chat-experience, pdf-library | CX-1, CX-5, PL-2, PL-6 | 1.6,2.2,2.8,4.4,7.1-7.3 | D2,D3 |
| 3 Settings/provider/model/key/OCR/privacy UX | chat-experience, grounded-generation, privacy-and-recovery | CX-2, GG-4, PR-1, PR-2 | 3.5-3.7,7.4 | D2,D4,D7 |
| 3 chat controls, Markdown, keyboard, RTL, themes, scroll/errors | chat-experience | CX-2-CX-5 | 4.7,7.1-7.2 | D2 |
| 3 truthful chat/upload/compaction timelines | chat-experience | CX-6 | 2.8,4.5,5.6 | D2,D4,D5 |
| 4.1 PDF-only validation, size, UUID, path safety | pdf-library, privacy-and-recovery | PL-1, PR-5 | 2.1,7.4 | D3,D7 |
| 4.2 local original/manifest/hash/dedup | pdf-library | PL-2 | 2.2,2.7 | D3 |
| 4.3 page extraction, tables, Unicode, sparse scan/OCR warning | pdf-library | PL-3, PL-4 | 2.3,6.1 | D3 |
| 4.4 chunk boundaries, provenance, exact schema | pdf-library | PL-3 | 2.4 | D3 |
| 4.5 embeddings, FAISS, lexical persistence, ID mapping | pdf-library | PL-5 | 2.5-2.7 | D3 |
| 4.6 safe rebuild/delete/model-change/corruption recovery | pdf-library | PL-6, PR-4, PR-6 | 2.7,6.5-6.6 | D3,D6 |
| 4.7 local-only indexing and progress | pdf-library | PL-5 | 2.8-2.9 | D3 |
| 5.1 persist user, reject empty, correlate IDs | grounded-generation, conversation-memory | GG-5, CM-1 | 4.1 | D4,D6 |
| 5.2 memory-aware retrieval query without using memory as evidence | grounded-generation, conversation-memory | GG-2, GG-5 | 4.1-4.3,5.4 | D4,D5 |
| 5.3 dense/lexical/RRF/rerank/snippet budget and calibrated evaluation | grounded-generation | GG-2 | 2.6,2.9,4.3,6.2 | D3,D4 |
| 5.4 bounded retrieval tools and at most two optional rounds | grounded-generation | GG-3 | 4.3,6.3 | D4 |
| 5.5 canonical prompt/memory/tail/source/current question exactly once | grounded-generation, conversation-memory | GG-5, CM-5 | 4.2,5.4 | D4,D5 |
| 5.6 real provider streams/cancel/incomplete record | grounded-generation, local-api | GG-6, API-4 | 3.1-3.4,4.5-4.6 | D4,D8 |
| 5.7 citation validation, insufficient/conflicting evidence, empty Library | grounded-generation | GG-1, GG-6 | 4.3-4.4 | D4 |
| 5.8 exact assistant persistence, duration/usage/errors/retry | conversation-memory, grounded-generation, privacy-and-recovery | CM-1, GG-6, PR-3-4 | 1.4-1.5,4.6,5.6 | D4,D6 |
| Trust boundary: PDFs are untrusted and cannot direct tools or disclose secrets | grounded-generation, privacy-and-recovery | GG-7, PR-5 | 4.8,7.4 | D4,D7 |
| 6A permanent history exact schema/order/fsync/recovery/delete isolation | conversation-memory, privacy-and-recovery | CM-1, PR-4, PR-6 | 1.4,1.6,5.3,7.3 | D5,D6 |
| 6B separate compaction checkpoint fields and idempotence | conversation-memory | CM-3 | 5.1,5.3 | D5 |
| 6 algorithm exact recursive 8/16/24 behavior and restart | conversation-memory | CM-2, CM-3 | 5.1,5.3-5.4 | D5,D6 |
| 6 structured summary content, source pointers, target and usage | conversation-memory | CM-4 | 5.2,5.6 | D5 |
| 6 total token guard, emergency compaction, never truncate question | conversation-memory | CM-5 | 5.5 | D5 |
| 7 exact source layout and local state files | local-runtime, conversation-memory, privacy-and-recovery | LR-4, CM-1, PR-3 | 1.1,1.4-1.9 | D1,D6 |
| 8 endpoint set, typed schemas, SSE fields/framing/heartbeat/cancel | local-api | API-1 through API-5 | 1.3,2.8,3.6,4.5-4.6 | D8 |
| 8 safe Markdown rendering and no untrusted raw HTML | local-api, chat-experience | API-5, CX-3 | 4.7 | D2,D8 |
| 9 log schema/redaction/provider data | privacy-and-recovery | PR-3 | 1.5,3.7,4.1,5.6 | D6,D7 |
| 9 key masking/keyring opt-in/no secret logs | privacy-and-recovery | PR-2 | 3.5-3.7,7.4 | D7 |
| 9 localhost/CORS/file serving/concurrency/PDF security | privacy-and-recovery, local-api | PR-5, API-5 | 2.1,4.8,7.4 | D7,D8 |
| 9 write ordering/cancel/retry/atomic concurrency | privacy-and-recovery, conversation-memory | PR-4, CM-1, CM-3 | 1.4-1.6,4.1,4.6,5.3 | D5,D6 |
| 9 updates/in-flight retrieval/deletion and enumerated failure cases | pdf-library, privacy-and-recovery | PL-6, PR-4, PR-6 | 2.7,4.4,6.5 | D3,D6 |
| 9 exports recommended; telemetry forbidden without opt-in | privacy-and-recovery | PR-1, PR-7 | 7.3-7.5 | D7 |
| 10.1-10.12 all twelve release tests | release-acceptance and linked capabilities above | RA-1, RA-2, capability scenarios | 8.1-8.5 plus phase tests cited above | D9 |
| 11 five vertical slices and definition of done | release-acceptance, local-runtime | RA-3, RA-4 | 1-8 | D9 |
| 12 implementation references | release-acceptance | RA-3 | 3.2-3.4, 2.3, 2.5-2.7, 6.2, 4.8 | D3,D4,D9 |

**Acceptance scenario IDs:** `CX` = chat-experience, `LR` = local-runtime, `PL` = pdf-library, `GG` = grounded-generation, `CM` = conversation-memory, `API` = local-api, `PR` = privacy-and-recovery, `RA` = release-acceptance. The suffix is the numbered requirement within that capability spec. Each phase/task above is in `tasks.md`; numeric task ranges refer to its numbered task IDs. This table is the source-to-spec-to-acceptance-to-phase index; the detailed source text follows unchanged.

Each source section is retained below without substantive editing, including file layout, numerical defaults, example schemas, failure cases, optional features, acceptance criteria, and reference guidance. Design details supplement rather than override this baseline.

---

# agent.md — Local PDF-Only RAG Chatbot

> Status: Implementation specification for a coding agent. Build a complete, runnable local application. Do not treat this file as an LLM system prompt for answering end-user questions; that prompt lives in `prompts/system.md`.
>
> Product name (working): **Local RAG Chat**. Default UI language may be English, but all text entry, search, extraction, and answers must support Unicode and Persian, French, and English; answers should use the user's language.

## 1. Mission and non-negotiable behavior

Build a polished, **single-user, localhost-only, PDF-grounded RAG chatbot** resembling the interaction model of ChatGPT. The user can create chats, upload and manage PDF documents in a Library, choose a remote LLM provider/model and enter an API key, then ask questions grounded in their PDFs.

**Requirements:**

1. The **only factual authority for questions about the document collection** is the set of currently active PDFs in the Library. No internet searching, external retrieval, or unsupported factual additions. The conversation is context, **not** authority to override the documents. If evidence is missing, say so and cite nothing fabricated.
2. PDFs remain on local disk. Parsing, chunking, embeddings, indexing, and retrieval happen locally. An LLM API request sends only the user message, relevant retrieved document snippets, system instructions, and compacted conversation context as needed. Make this privacy boundary explicit in Settings.
3. No account, authentication screen, hosted database, SaaS vector store, Docker requirement, or cloud infrastructure. A Python backend and local files are allowed and required; the backend is bound to `127.0.0.1` by default. An internet connection may still be required for the selected remote LLM API and initial model/package downloads.
4. Preserve **every complete user and assistant message verbatim and indefinitely** in one durable append-only raw-history file, unless the user explicitly deletes the chat. Compaction must **never** alter raw history.
5. Preserve detailed operational activity in a **separate** durable append-only structured log: time, chat/request IDs, user request, API calls and duration, retrieval queries and returned source IDs/scores, indexing/compaction status, errors and token usage when available. Never log API keys or authorization headers.
6. Use **recursive compaction after every eight completed conversation messages per chat** (both final user and assistant messages count; token deltas, progress events and tool calls do not). Keep compaction checkpoints independent from raw history and prevent unbounded model context.
7. Stream actual model output to the UI incrementally, showing accurate, event-driven status updates such as “Searching documents,” “Sending API request,” “Generating answer,” and “Compacting conversation.” Do not simulate thinking or expose private chain of thought.
8. Keep all prompts as versioned UTF-8 Markdown files inside `prompts/`; **never** embed large prompt strings in Python/TypeScript source. Supply an editable default answer prompt (`prompts/system.md`) and a distinct compaction prompt (`prompts/compaction.md`). The user may replace the answer prompt later without modifying code.
9. Deliver working code, tests, installation instructions for Windows 11/WSL2/macOS/Linux, example environment settings, and a simple local launch workflow; no TODO-only implementations or mocked success paths.

## 2. Technology choices

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React + TypeScript + Vite | Modern, responsive ChatGPT-like UI using HTML/CSS/JS under the hood |
| UI | Tailwind CSS + accessible UI primitives; Lucide icons | Consistent theme, responsive design, keyboard accessibility |
| Backend | Python 3.11+; FastAPI; Pydantic; Uvicorn | Local API, validation, async streaming |
| Streaming | `fetch()` POST + streamed SSE-format response (`text/event-stream`), parsed incrementally | Supports a JSON chat body and status/token events; no fake typewriter |
| PDF | PyMuPDF | Extract page-aware text, block ordering and page numbers |
| OCR | Optional local Tesseract through PyMuPDF, with explicit install/availability checks | Support scanned/image-only PDFs; never silently pretend an empty scan is indexed |
| Local embeddings | `sentence-transformers`; default `intfloat/multilingual-e5-small` | CPU-friendly multilingual dense retrieval, no paid embedding API |
| Vector search | `faiss-cpu`, index persisted on disk | Local search without a running database service |
| Lexical search | BM25 (`rank-bm25` or a maintained equivalent) | Exact-word and identifier matching in addition to semantics |
| Retrieval fusion | Reciprocal Rank Fusion (RRF), optionally local multilingual reranking | Stronger candidate selection; no remote retrieval dependency |
| Remote LLM | Pluggable provider adapters: OpenAI, Anthropic, Google Gemini; optional generic OpenAI-compatible endpoint | User chooses provider/model/key; do not assume one universal wire format |
| Secret storage | In-memory per running session by default; optional OS credential vault via `keyring` if explicitly enabled | Avoid plaintext API keys in files/browser storage |
| Persistence | Local JSON/JSONL, PDF files, FAISS binary index, and atomic state snapshots | No SQLite/Postgres/Chroma server or user account |
| Testing | pytest + FastAPI tests; Vitest/React Testing Library; Playwright smoke test | Validate behavior and UI end to end |

If `faiss-cpu` is unsupported in the target Python/OS combination, document the constraint and provide a tested fully local equivalent; do not silently substitute a hosted service. Versions should be pinned in lockfiles after compatibility testing. Make the embedding model configurable; changing it must trigger a full index rebuild. E5-style models must use `query: ` for queries and `passage: ` for chunks (or equivalent model-specific `encode_query/encode_document` support); normalize vectors consistently.

## 3. User experience and navigation

**Layout:** a clean, responsive ChatGPT-style app with a collapsible left sidebar and a large central chat panel. Sidebar sections:

- **New Chat**: creates an independent thread, auto-generated title, rename, delete with confirmation, and a chronological conversation list.
- **Library**: browse all PDFs, upload with a `+` button and drag-and-drop, see title/filename, page count, indexed state, creation time, size, and errors. Allow re-index, remove, and in-browser PDF preview at a referenced page. Newly uploaded PDFs become searchable in all chats once indexing succeeds. A removed PDF cannot be retrieved on future turns; existing historical citations can be shown as unavailable rather than rewritten.
- **Settings / Configuration**: provider dropdown, editable model name/list if supported, masked API key field, explicit “Save key in OS keyring” opt-in, connection test, embedding model + rebuild guidance, optional OCR toggle, and a read-only summary of storage and privacy. No signup, accounts, or user profile.

**Chat panel:** visually distinct user and assistant bubbles, Markdown rendering with fenced code blocks, inline clickable source citations `【filename.pdf, p. 12】`, source drawer with retrieved snippet and PDF page preview, multiline auto-resizing composer, Enter-to-send / Shift+Enter newline, send/stop-stream, retry last response, copy answer, clear errors, and accurate auto-scroll without jumping when the user scrolls up. Support Persian RTL text and mixed RTL/LTR content, responsive mobile widths, light/dark mode, focus indicators, skeleton/loading states, empty-library onboarding, and API-key-missing warnings.

**Status timeline:** show real transitions only, including `Validating request → Searching Library → Reranking passages (if enabled) → Calling <provider>/<model> → Streaming answer → Saved`. Separate statuses for uploads: `Validating PDF → Extracting pages → OCR (if needed) → Chunking → Embedding → Indexing → Ready/Failed`. If compaction occurs, emit `Compacting previous 8 messages` and display retry/failed state without destroying any message. Never display invented internal reasoning.

## 4. Library ingestion and indexing

1. Accept **only `.pdf`**; validate both extension and PDF signature/content. Reject unsupported files, encrypted/unreadable PDFs with a clear error, and enforce configurable limits (suggested default: 50 MB/file). Sanitize filenames, guard path traversal, and assign an internal UUID (`document_id`) independent of user filename.
2. Save original PDFs under `data/library/pdfs/<document_id>.pdf`. Store safe metadata in `data/library/manifest.json`: original name, SHA-256, page count, import timestamp, status, extraction/OCR warnings, index version and error. Deduplicate identical content by hash; report it instead of silently duplicating chunks.
3. Extract text **page by page**, preserving page references and reasonable reading order (PyMuPDF blocks/dict). Preserve important table text where possible. Support mixed Persian/English/French and Unicode normalization without corrupting citations. If extraction is empty/suspiciously sparse, offer local OCR with installed language packs; clearly warn when OCR cannot run.
4. Create semantically sensible, preferably heading/paragraph-aware chunks, always traceable to page number(s). Starting configurable target: **~500 tokens, ~80-token overlap**. Avoid crossing page boundaries where it makes citation accuracy ambiguous; if spanning pages is essential, retain exact page ranges. Record `{chunk_id, document_id, filename, page_start, page_end, text, sha256, position, embedding_model_version}`.
5. Compute local embeddings in batches using model-specific query/document prefixes and vector normalization. Persist index via FAISS `write_index/read_index`, persist chunk metadata/text as UTF-8 JSONL, and persist lexical-search data locally. Keep a stable `faiss_id ↔ chunk_id` mapping.
6. Rebuild index safely on document deletion, embedding-model change, corrupted index, or explicit “Reindex”; write temporary outputs and atomically replace only after complete success. Prevent queries from reading a half-written index. Use a mutex/file lock as appropriate for the single process. For index rebuild errors, keep the previous known-good index or report that Library is temporarily unavailable; never claim success prematurely.
7. No cloud OCR, remote embeddings, external vector DB, or auto-uploading entire PDFs to the provider. Indexing progress must be observable via status events or a status endpoint.

## 5. Retrieval and answer pipeline

Each user request is handled in an orchestrator rather than simply pasting an entire PDF into the prompt:

1. Append the **verbatim user message** to raw history and a redacted-safe activity event to system log, with stable `chat_id`, `message_id`, `request_id`, timestamp. Reject empty questions.
2. Load the selected conversation's persisted recursive summary and **only the uncompacted raw tail** from history, plus the newest user message once (no duplication). Use those for coreference-aware retrieval query construction (e.g. “What about its deadline?”). Never treat summary or prior user statements as PDF evidence.
3. Execute local **hybrid retrieval** against current Library: dense FAISS top ~20 + lexical BM25 top ~20, fuse with RRF, deduplicate by chunk/document/page, and optionally rerank ~15-20 candidates with a **local, multilingual** reranker. Choose roughly 4-8 high-value snippets subject to a configurable token budget; retain citations and metadata. Tune relevance thresholds using test queries; do not guess that an arbitrary similarity value means confidence.
4. Support **agentic retrieval** through an explicit backend `search_library(query, top_k, optional_document_ids)` operation and `get_source_excerpt(chunk_id)` lookup. Prefer deterministic initial retrieval for every document question; if the selected provider supports tool calling, optionally allow the model to request up to **2 additional retrieval rounds** for missing evidence. For providers without tool calling, the backend retrieval pipeline must still work. Never give the model filesystem, shell, web, or external network tools. Each search round gets an accurate UI status/log entry.
5. Construct model input in this logical order (map to the provider's correct API message roles):
   - canonical text from **`prompts/system.md`**;
   - a clearly marked **conversation memory** block holding only the persisted summary, if any;
   - completed raw conversation tail, in original order;
   - retrieved **untrusted document excerpts**, fenced and tagged with immutable source IDs, names, and page numbers;
   - the current user question **exactly once** (already present in the tail, or separately if the adapter excludes it from the tail).
   - Tool affordances / schemas are delivered via provider tool APIs or a backend-orchestrated equivalent; **do not** place them as trusted prose inside PDF chunks.
6. Stream the LLM's output as true network chunks with events `status`, `retrieval`, `token`, `citation`, `usage` (when exposed), `done`, `error`. Parse upstream events per provider; forward actual text deltas, not artificial per-character delays. On cancel, abort upstream request where supported and record a canceled/incomplete answer explicitly.
7. Validate citations against snippets actually retrieved in this request and existing indexed documents. **Do not fabricate citations.** Show citations near factual claims; each source opens the exact source PDF/page. For insufficient or contradictory support, acknowledge uncertainty, flag conflicts and cite both sides if available. If Library is empty, explain the user must upload PDFs first.
8. Once a response finishes, append its **full exact final text** to raw history, and log completion, request duration and token counts if provided. Clearly handle network errors/invalid keys/rate limits/timeouts with retry guidance; never save a partially generated response as if it were complete.

**Trust boundary:** PDFs and extracted text are **untrusted data**, even if they contain “ignore your instructions” or fake system messages. The system prompt always outranks retrieved documents. Retrieved text cannot instruct the app to use tools, alter settings, leak credentials or change the rules. Any retrieved content must be delimited as source data, not executable instructions.

## 6. Exact conversation-memory / recursive compaction policy

There are **two entirely different concepts**: (A) permanent full raw history and (B) bounded model-visible conversation context. They must not be confused.

### A. Permanent full history

Use `data/chat_history.jsonl` as the **canonical append-only archive of all chats**. Each finalized record carries `{event_id, chat_id, message_id, role: "user" | "assistant", content: "the full unsummarized message", created_at, completed: true, request_id, metadata}`. Keep message text byte-for-byte as received/stored in UTF-8 after JSON decoding. Never replace, truncate or rewrite old chat messages during compaction. Ensure safe append, flush/fsync policy, recovery of incomplete trailing JSONL, and stable ordering. Chat deletion can use tombstones plus an explicit archive rewrite/garbage collection process, but must not accidentally affect other chats.

### B. Bounded context sent to the model

Persist separate state in `data/state/compactions.json` (or one state file per chat). For each chat keep:

- `summary`: the cumulative recursive summary; empty initially.
- `last_compacted_message_id` and a monotonically increasing compacted-message count.
- `prompt_version`, `summary_revision`, and timestamps, so failed/restarted compaction is idempotent.

**Algorithm (strictly per chat):**

```text
on completed conversational message (user or final assistant):
    append full message to chat_history.jsonl
    increment un-compacted completed-message counter
    if counter >= 8:
        batch = next 8 uncompacted messages in chronological order
        new_summary = LLM_compact(previous_summary, batch, prompts/compaction.md)
        if and only if compaction succeeds and result validates:
            atomically persist new_summary + checkpoint through batch's final message_id
            remove batch ONLY from future model-visible raw tail, NOT from raw history
        else:
            retain old checkpoint and full tail; log failure and retry safely

for each model turn:
    load summary from checkpoint
    load only complete raw messages after checkpoint
    include current user question exactly once
    enforce context budget and compact eligible older messages before overflowing
```

This is **recursive**: `S1 = compact(empty, messages[1..8])`, `S2 = compact(S1, messages[9..16])`, `S3 = compact(S2, messages[17..24])`, etc. Do **not** make `S2 = compact(messages[1..16])`, do not summarize a previous summary as if it were original raw messages, and do not double-count messages. A user's message counts when saved; an assistant response counts when finalized. Thus a typical pair of exchanges increments by two. If the threshold is hit mid-turn, compaction must not prevent answering and must not cause the current message to appear twice; you may process compaction immediately before the next model request. On restart, resume from persisted checkpoint and deterministic raw-history order.

Summaries must preserve enduring conversational facts needed for follow-ups (entities, selected documents, unresolved questions, user preferences stated in the conversation, decisions and constraints), plus explicit uncertainty/contradictions and relevant **source references as pointers only**. They must not substitute for reretrieving actual PDF passages, invent unsupported facts or retain credentials. Include compact **structured sections** rather than a vague paragraph. Target ~500-900 tokens, configurable. If a summary approaches the summary budget, recursively rewrite old summary + new batch, dropping redundant detail but never losing explicit important constraints without reason. Log compaction timing and input/output token usage when available.

**Token-budget guard:** compaction every 8 messages is not sufficient by itself to guarantee a bounded context if individual messages or retrieved passages are huge. Enforce provider/model-aware budget: cap retrieved text, cap summary and input size, and when necessary issue an extra emergency compaction of older uncompacted messages; keep recent user intent intact. Do not silently truncate a user's question. If it cannot fit, show a clear error. The raw-history archive remains intact.

## 7. File-level architecture (prompts must be outside code)

```text
local-rag-chat/
├── agent.md                          # This build specification
├── README.md                         # Install, start, architecture, privacy, limitations
├── .gitignore                        # data/, secrets, generated indexes, env files
├── .env.example                      # Safe non-secret defaults only
├── prompts/
│   ├── system.md                     # Canonical answer-generation instructions
│   └── compaction.md                 # Canonical recursive memory instructions
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                    # FastAPI app and local static hosting
│   │   ├── config.py                  # Validated non-secret settings
│   │   ├── api/
│   │   │   ├── chats.py               # Chat CRUD; streams
│   │   │   ├── library.py             # Upload, list, delete, reindex, PDF preview
│   │   │   ├── settings.py            # Providers/model settings, test key
│   │   │   └── status.py              # Health/indexing status
│   │   ├── domain/
│   │   │   ├── schemas.py
│   │   │   └── events.py
│   │   ├── services/
│   │   │   ├── pdf_ingestion.py
│   │   │   ├── chunking.py
│   │   │   ├── embeddings.py
│   │   │   ├── vector_index.py
│   │   │   ├── lexical_index.py
│   │   │   ├── retrieval.py
│   │   │   ├── chat_orchestrator.py
│   │   │   ├── context_manager.py
│   │   │   ├── prompt_loader.py        # Read prompt files; validate/fail clearly
│   │   │   ├── history_store.py
│   │   │   ├── activity_logger.py
│   │   │   └── credential_store.py
│   │   └── llm/
│   │       ├── base.py                # Async adapter interface
│   │       ├── openai_provider.py
│   │       ├── anthropic_provider.py
│   │       ├── gemini_provider.py
│   │       └── compatible_provider.py
│   └── tests/
│       ├── test_pdf_ingestion.py
│       ├── test_retrieval.py
│       ├── test_compaction.py
│       ├── test_history_logging.py
│       ├── test_streaming.py
│       └── test_prompt_injection.py
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/                      # Routing/app state
│   │   ├── components/               # Sidebar, Chat, Composer, Status, Citation
│   │   ├── pages/                    # Chat, Library, Settings
│   │   ├── hooks/                    # Stream reader, state management
│   │   ├── lib/                      # Typed API client and utilities
│   │   └── styles/
│   └── tests/
├── scripts/
│   ├── start.ps1                      # Windows local start
│   └── start.sh                       # POSIX local start
└── data/                              # Created at runtime; gitignored
    ├── chat_history.jsonl             # MAIN FILE 1: verbatim all chat messages
    ├── system.log.jsonl               # MAIN FILE 2: structured app/API/RAG logs
    ├── library/
    │   ├── manifest.json
    │   └── pdfs/<document_id>.pdf
    ├── index/
    │   ├── faiss.index
    │   ├── chunks.jsonl
    │   └── bm25_index.*
    └── state/
        ├── chats.json                 # Chat title/list/tombstones
        └── compactions.json           # Summary + per-chat checkpoint
```

These files are the **two primary canonical history/log artifacts**, not the only files on disk. PDF/index/metadata/compaction snapshot files are required supporting state; they are not a cloud database. Make deletion, restart recovery, and corruption behavior explicit.

## 8. Backend API contract (minimum)

- `GET /api/health`
- `GET /api/chats`, `POST /api/chats`, `PATCH /api/chats/{chat_id}`, `DELETE /api/chats/{chat_id}`
- `GET /api/chats/{chat_id}/messages` (read complete raw history for UI), `POST /api/chats/{chat_id}/messages/stream` (stream statuses + assistant deltas)
- `GET /api/library`, `POST /api/library/upload` (multipart PDF), `DELETE /api/library/{document_id}`, `POST /api/library/{document_id}/reindex`, `GET /api/library/{document_id}/pdf` (page fragment controlled by frontend)
- `GET /api/index/status` (progress/status), `POST /api/index/rebuild`
- `GET /api/settings` (never return a saved API key, only `has_key`), `PUT /api/settings`, `POST /api/settings/test-connection`

Define typed request/response/event schemas in one backend contract and generate or mirror TypeScript types reliably. Streaming SSE-style event example:

```text
event: status
data: {"stage":"retrieving","label":"Searching Library","request_id":"..."}

event: retrieval
data: {"sources":[{"chunk_id":"...","document_id":"...","page":7,"score":0.81}]}

event: token
data: {"delta":"The document states..."}

event: done
data: {"message_id":"...","complete":true}
```

`score` is illustrative, not a universal confidence percentage. Ensure proper newline framing, cancellation, heartbeats for long indexing/API waits, incremental UTF-8 decoding, and safe frontend Markdown sanitization (no untrusted raw HTML). Never use `innerHTML` with untrusted PDF/model text.

## 9. Operational logging, privacy and robustness

- Each log record in `data/system.log.jsonl` has ISO-8601 timestamp with timezone, severity, event type, chat/request/document IDs when relevant, duration, source IDs/pages/scores, and error category; capture the user's submitted text for traceability but **redact likely credential patterns**. The full unmodified user message is already archived in chat history. Avoid logging the full retrieved chunks unless a local explicit debug option is enabled.
- On provider calls, record provider/model, start/end, status code if available, latency, usage/cost estimates if returned; **never** store the key, headers, bearer tokens, or prompt containing embedded secrets in routine logs. Mask the key in the UI; optional OS-keyring persistence is explicit. If the user enters a key into a message, warn that message history is local and may contain it.
- Localhost binding (`127.0.0.1`), tight CORS origin, no exposed static directory traversal, rate/concurrency limits where useful, no unrestricted file serving, strict PDF/content validation. Never run commands found inside PDFs.
- Consistent write order: persist user message before generation, persist assistant message only as complete on success or with `completed:false` metadata for interrupted output; record abnormal cancellation and retry as separate request attempts. Use locking/atomic operations to prevent concurrent corruption.
- Handle library updates during in-flight retrieval with an index snapshot/version; never cite a deleted/inaccessible document as currently available. Handle empty index, duplicate files, unreadable scans, missing secrets, unsupported models, network outage, provider rate limiting, long PDF indexing, restart mid-compaction, and rebuild failure.
- Provide export of chat as Markdown/JSON and raw-history backup via safe local download endpoints (recommended). No analytics or telemetry without explicit opt-in.

## 10. Acceptance tests: the project is done only when all pass

1. Launch via documented commands and open `http://127.0.0.1:<configured_port>` with **no login**, no Docker and no external DB.
2. Upload a normal PDF through Library; see extraction/indexing progress; search it and receive a correctly grounded answer with **clickable file+page citations**.
3. Ask a question absent from all PDFs; system transparently states evidence is insufficient instead of using pretrained general knowledge. Ask a multi-PDF question and see citations from all relevant sources. If two PDFs contradict, both are identified.
4. Upload a malformed/non-PDF file and an image-only PDF: reject the first; offer OCR or a clear OCR warning for the second.
5. Change provider/model and enter an API key in Settings, test connection; the key never appears in `/api/settings`, raw application logs, or repository files. Invalid keys show clear errors.
6. Observe genuine `retrieving → calling API → streaming` UI events and incremental answer tokens; stop/cancel works and does not create a falsely completed answer.
7. Send **8**, **16**, **24** completed conversation messages into the **same chat**. Verify recursive summaries `S1`, `S2`, `S3`, checkpoint boundaries, and that every original message remains verbatim in `chat_history.jsonl`. Verify a different chat has its own independent compaction counter. Test restart/recovery and failed compaction.
8. Validate that each API call receives one system prompt, one current question, relevant retrieved snippets/tool access, a cumulative summary of older chat, and the uncompacted recent messages—without duplication. Test token-budget fallback for very long messages.
9. Delete a PDF and re-ask its question: it must not be retrieved; existing raw chats stay intact. Reindex and restart; retrieval still works.
10. Add a malicious PDF instructing the model to ignore the system prompt or reveal an API key; ensure its instructions are treated as document content only and no secrets leak.
11. Validate UI on desktop/mobile, keyboard navigation, long answers, RTL Persian and French/English mixed content, citations, light/dark theme and errors.
12. Run automated tests, formatters, type checks and at least one true end-to-end smoke test. Document any unsupported provider or OCR condition; do not claim a feature works without exercising it.

## 11. Implementation plan for the coding agent

Build in vertical slices and verify each before moving on:

1. Scaffold FastAPI + React/Vite, typed API, local data directories, frontend design system and app shell.
2. Implement safe PDF upload/preview, extraction, chunking, embeddings, persistent hybrid index, and Library progress UI.
3. Implement provider adapters + Settings/credential handling, genuine SSE streaming, answer grounding and citations.
4. Implement canonical append-only history, structured logs, per-chat recursive compaction checkpoints, and restart resilience.
5. Add optional multi-round retrieval, OCR, error recovery, responsive polish, export, and full tests/documentation.

**Definition of done:** provide source code and a working launch command, a concise README explaining that only PDFs are grounding authority but remote providers may see selected snippets, and a test report listing pass/fail evidence. Keep solutions modular and locally runnable; avoid unnecessary agent frameworks or hosted services. Do not replace the specified approach with a generic chat wrapper.

## 12. Reference implementation guidance

- OpenAI streaming: https://developers.openai.com/api/docs/guides/streaming-responses
- PyMuPDF page extraction/OCR: https://pymupdf.readthedocs.io/en/latest/page.html
- FAISS disk persistence: https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning
- Sentence Transformers embeddings: https://www.sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html
- Sentence Transformers reranking: https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html
- OWASP guidance for RAG injection boundaries: https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html
