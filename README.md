# Ragforge

[▶ Watch the Ragforge demo](docs/media/ragforge-demo.mp4)

[![CI](https://github.com/rashidiff/ragforge/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/rashidiff/ragforge/actions/workflows/ci.yml)

**Chat with your PDFs. Keep your document library and conversation history on your machine.**

Ragforge is a single-user workspace for conversations grounded in a local PDF library.
It combines local document processing and hybrid search with a configurable LLM
provider, streamed answers, page-level citations, and persistent conversation memory.

The application runs on localhost without Docker, a login, or an external database.
Answer generation uses your selected provider; relevant excerpts and conversation
context may leave your machine. See [Privacy and storage](#privacy-and-storage).

## Features

- **A persistent PDF library** — upload or drag in PDFs, follow indexing progress,
  preview source pages, and reindex or remove documents.
- **Local hybrid retrieval** — multilingual sentence embeddings, FAISS vector search,
  BM25 keyword search, and reciprocal rank fusion.
- **Grounded conversations** — retrieved PDF excerpts inform answers; validated
  citations open the corresponding source page.
- **Configurable providers** — OpenAI, Anthropic, Google Gemini, and optional
  OpenAI Responses-compatible endpoints with explicit capability configuration.
- **Streaming and recovery** — streamed output, Stop, retry, incomplete-answer labels,
  and durable history across restarts.
- **Recursive conversation memory** — per-chat summaries compact completed messages
  in batches of eight while preserving the original archive. Smaller emergency
  batches can recover context budget when needed.
- **A multilingual interface** — English and French, with Unicode document/message support,
  light/dark themes, keyboard controls, and responsive navigation.
- **Portable history** — Markdown and JSON chat exports plus raw-history backups.

Optional enhancements include local Tesseract OCR, multilingual reranking, and
bounded provider tool calls that can search the local library or request excerpts.

## Quick start

### Requirements

- **Python 3.11+** — CI currently checks Python 3.11 on Ubuntu.
- **Node.js 22+** and npm.
- Internet access for dependency and initial embedding-model downloads, and for
  remote LLM requests.
- A provider account and API key to generate answers from indexed documents.
  Enter the key in the application's Settings page.

Windows PowerShell, WSL2, macOS, and Linux startup instructions are provided below.
A successful Ubuntu CI run does not establish compatibility on every platform.

### 1. Get the source

```sh
git clone https://github.com/rashidiff/ragforge.git
cd ragforge
```

### 2. Install dependencies

The `rag` extra installs local PDF/indexing dependencies. The `providers` extra
installs HTTP integration and optional OS credential-vault support.

**Windows — PowerShell**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[rag,providers]"
cd frontend
npm install
cd ..
```

**macOS, Linux, or WSL2**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[rag,providers]'
cd frontend
npm install
cd ..
```

For WSL2, keep the checkout, Python environment, and Node installation inside the
same WSL distribution. The first PDF indexing job downloads the configured local
embedding model; allow time and disk space for that initial setup.

### 3. Start the workspace

Start the backend from the repository root and keep its terminal open:

| Platform | Backend command |
| --- | --- |
| Windows PowerShell | `.\scripts\start.ps1` |
| macOS, Linux, WSL2 | `sh scripts/start.sh` |

In a second terminal, start the frontend:

```sh
cd frontend
npm run dev
```

Open **[http://127.0.0.1:5173](http://127.0.0.1:5173)**.
The frontend proxies API requests to the backend at `127.0.0.1:8000`.
Stop either process with **Ctrl+C**.

### 4. Ask your first question

1. Open **Settings**, select a provider, enter its API key, and save. Choose the
   model from the **LLM model** dropdown at the top of the chat. You can test the
   connection in Settings using that selection (or the provider default).
2. Open **Library** and upload a text-based PDF. Wait for indexing to finish.
3. Start a chat and ask a question about the document.
4. Open an answer's citation to inspect the supporting page and excerpt.

If the library is empty or no relevant evidence is retrieved, the application
returns an evidence-limited response. Retrieval quality and generated answers
should still be reviewed against the cited sources.

See [model selection and provider catalogs](docs/model-selection.md) for the reviewed
model list, account-access caveats, custom endpoints, and selection behavior.

## Configuration

Defaults work without an `.env` file. To customize non-secret configuration, copy
[`.env.example`](.env.example) to `.env` in the repository root.
**Keep provider API keys out of `.env`, source files, and chat messages.**

| Setting | Default | Purpose |
| --- | --- | --- |
| `RAG_PORT` | `8000` | Local backend port |
| `RAG_DATA_DIR` | `data` | PDFs, history, logs, and index storage |
| `RAG_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Local embedding model |
| `RAG_MAX_UPLOAD_BYTES` | `52428800` | 50 MiB PDF upload limit |
| `RAG_OCR_ENABLED` | `false` | Optional local OCR |
| `RAG_OCR_LANGUAGES` | `eng+fra+fas` | Required Tesseract language packs when OCR is enabled |

Relative storage and prompt paths resolve from the repository root. Changing the
embedding model requires rebuilding the index. OCR also requires a local Tesseract
installation and the configured language packs; it is not enabled by installing
Python dependencies alone.

For a different backend port, set `RAG_PORT` and set `RAG_API_PROXY` in the frontend
terminal to the matching local origin. `RAG_DEV_ORIGIN` must match the frontend's
actual origin. The backend binds to `127.0.0.1`.

The answer and compaction instructions live in editable UTF-8 Markdown files:
[`prompts/system.md`](prompts/system.md) and
[`prompts/compaction.md`](prompts/compaction.md).
See [PDF processing and recovery](docs/library.md) for model downloads, OCR, and tuning.

## Architecture

```text
PDF upload → validation → page extraction / optional OCR → chunks
                                                         ↓
                                             local embeddings + FAISS / BM25
                                                         ↓
Question + conversation context → hybrid retrieval → selected excerpts
                                                         ↓
                                             configured LLM provider
                                                         ↓
                                       streamed answer + validated citations
```

React and TypeScript provide the interface; Vite builds the frontend. FastAPI and
Pydantic define the backend and public contracts. PDFs are processed with PyMuPDF;
Sentence Transformers provides local embeddings. JSON/JSONL files and immutable
index generations provide persistence without an external database.

| Directory | Contents |
| --- | --- |
| `frontend/` | React interface, component tests, and Playwright scenarios |
| `backend/app/` | API routes, provider adapters, retrieval, and persistence services |
| `backend/tests/` | Automated unit, integration, and failure/recovery tests |
| `prompts/` | Editable answer and compaction prompts |
| `docs/` | Integration contracts, configuration, privacy, and recovery guides |
| `openspec/` | Product specifications, architecture decisions, and implementation tracking |
| `.github/workflows/` | Hosted CI and formatting maintenance |

## Privacy and storage

PDF parsing, chunking, embeddings, indexing, and retrieval run locally. The selected
LLM provider receives instructions, your question, selected PDF excerpts, and
necessary conversation context. Entire PDF files are not uploaded by the provider
adapters. Ragforge is therefore a local document workspace with remote generation,
not a fully offline LLM application.

Provider keys stay in session memory by default. Saving a key to the OS credential
vault is an explicit opt-in. Keys are not returned by the settings API or saved in
browser local storage. Browser storage holds only non-sensitive interface preferences.

The default `data/` directory contains:

- Original PDFs and the library manifest.
- The verbatim `chat_history.jsonl` archive.
- Separate redacted operational logs in `system.log.jsonl`.
- Chat metadata, compaction checkpoints, indexing jobs, and local search generations.

**Local data and exports are not encrypted by the application.** History preserves
what you send, including any sensitive text. Compaction does not rewrite the original
messages. Removing a PDF excludes it from future retrieval; historical citations
can become unavailable. Deleting a chat removes its active history, but previous
backups may still contain it.

Use OS account/disk protections for private documents and backups. If storage is
corrupt, preserve the data directory before recovery rather than replacing files
with empty ones. See [conversation memory and recovery](docs/conversation-memory.md).

## CI and verification

[GitHub Actions](https://github.com/rashidiff/ragforge/actions/workflows/ci.yml)
runs automatically on pushes and pull requests:

| Backend | Frontend |
| --- | --- |
| pytest unit and integration tests | Vitest component and library tests |
| Ruff lint and formatting checks | Mocked Chromium Playwright integration |
| mypy type checking | ESLint and Prettier checks |
| | TypeScript type checking and production build |

CI uses temporary test storage, mocked LLM adapters/transports, and no paid provider
calls or real API keys. Both jobs passed in
[the verified baseline run](https://github.com/rashidiff/ragforge/actions/runs/43252817718).
The badge above shows the current workflow status.

Passing CI establishes the automated checks, including a mocked browser flow.
Live-provider acceptance, real embedding-model behavior, retrieval-quality evaluation,
OCR installations, and the full supported-platform matrix remain separate release
gates. See [CI details](docs/ci.md), [release acceptance](docs/verification.md), and
[the live integration scenario](docs/e2e.md).

## Documentation

- [PDF library, local models, OCR, and index recovery](docs/library.md)
- [Provider capabilities and data boundaries](docs/provider-capabilities.md)
- [Streaming, cancellation, retries, and citations](docs/streaming-contract.md)
- [Recursive memory, context budgets, and durable history](docs/conversation-memory.md)
- [Product specifications and roadmap](openspec/changes/initial-project-documentation/)

## Contributing

Open an issue with reproduction steps and the relevant CI output. For code changes,
include focused automated coverage and use the hosted CI checks before merging.
Do not attach private PDFs, provider keys, raw conversation archives, or unredacted
logs to issues or pull requests.
