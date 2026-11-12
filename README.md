# Local RAG Chat

[![CI](https://github.com/rashidiff/ragforge/actions/workflows/ci.yml/badge.svg)](https://github.com/rashidiff/ragforge/actions/workflows/ci.yml)

A single-user localhost workspace for PDF-grounded conversations. The project is
being implemented from `agent.md` through the OpenSpec change
`initial-project-documentation`.

**Current code:** local settings and credential handling, durable raw history and
redacted activity logs, atomic chat metadata/deletion, editable prompt loading, chat
CRUD, the PDF Library and local hybrid index, provider adapters, grounded streaming,
citations, recursive memory, context budgeting, and compaction status/retry surfaces
have been written. Automated tests are authored alongside the code. None of these
features has been tested or verified yet, and release acceptance remains incomplete.
Do not treat the current code as a verified or release-ready RAG product.

No tests, dependency installations, builds, formatters, type checks, or browser
checks have been executed locally during implementation. Dependency ranges are
declared; tested lockfiles and a supported-platform matrix remain pending. See
`docs/verification.md` for release acceptance detail and [`docs/ci.md`](docs/ci.md)
for the GitHub Actions checks. Automated suites, formatters, linters, type checks,
and builds are configured to run on Actions for every push and pull request; no CI
run has been executed or reported yet. Replace `rashidiff/ragforge` in the badge URL
after creating or selecting the GitHub repository.

## Prerequisites

- Python 3.11 or newer; Python 3.11/3.12 are sensible first environments to assess
  before adding local ML packages.
- Node.js 22 or newer and npm.
- Windows 11 PowerShell, WSL2, macOS, or Linux. Each environment is currently
  **unverified**; the commands below are provided for manual execution.
- Internet access for initial dependency/model downloads and when using the selected
  remote LLM provider. No Docker, account, or external database.

## Install and run — Windows 11

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
cd frontend
npm install
cd ..
.\scripts\start.ps1
```

Keep that backend terminal open. In a second terminal:

```powershell
cd frontend
npm run dev
```

Open [the Vite development UI](http://127.0.0.1:5173). It proxies `/api` to the
backend at port 8000. The backend itself binds only to `127.0.0.1` and its health
endpoint is [local API health](http://127.0.0.1:8000/api/health). Stop either
foreground process with Ctrl+C. An empty workspace needs no model download. To index
PDFs, install the optional RAG dependencies described in `docs/library.md`.

## Install and run — WSL2, macOS, Linux

Install Python/Node through your operating system's supported package workflow,
then from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
cd frontend
npm install
cd ..
sh scripts/start.sh
```

In another terminal, run `cd frontend` followed by `npm run dev`. In WSL2, keep
the source, Python environment and Node installation in the same WSL distribution;
use the WSL address forwarding to reach the local UI from the Windows browser.
Native Windows and WSL Python environments are separate.

## Serve one local production address

When you choose to build the frontend manually:

```sh
cd frontend
npm run build
```

Return to the root and start the backend with the platform's start script. FastAPI
serves the built frontend at [the local app](http://127.0.0.1:8000), without a second
server or login. Until built assets exist, `/` returns an explicit 503 response
rather than pretending the UI is available. Production build behavior is unverified.

## Configuration and prompts

Defaults require no `.env`. Copy `.env.example` to `.env` to change non-secret
configuration. Relative paths resolve from the repository root, independent of
the process working directory. The host is constrained to `127.0.0.1`; invalid
ports, remote development origins and incompatible budgets fail validation.

For a custom backend port, change `RAG_PORT`; also set `RAG_API_PROXY` in the
frontend terminal to the full new local backend origin before running Vite.
`RAG_DEV_ORIGIN` must match the actual Vite origin, including its port. Use
`127.0.0.1`, not a public bind address.

- `prompts/system.md` is the canonical answer-generation prompt.
- `prompts/compaction.md` is the distinct recursive-memory prompt.
- Both are UTF-8 Markdown, loaded at use time and versioned by SHA-256. Editing
  them requires no source-code edit. Missing, empty, invalid UTF-8 or escaped-path
  prompts fail clearly at startup. `agent.md` is never used as an answer prompt.

## Architecture and local data

React/TypeScript/Vite with Tailwind, Lucide and an accessible confirmation dialog
calls the Python/FastAPI API. Domain Pydantic schemas define public payloads.
Routes delegate to local stores and services. Static hosting serves only the
configured frontend distribution; API misses cannot fall through to the SPA.
Only one backend writer may hold a given data root at a time.

Runtime creates these local paths (all excluded from version control):

```text
data/
  chat_history.jsonl       # canonical, verbatim messages for all chats
  system.log.jsonl         # separate, redacted structured operational events
  state/chats.json        # atomic metadata, tombstones and GC status
  state/compactions.json  # atomic recursive-memory checkpoints
  state/index_jobs.json  # persistent progress and interrupted job status
  library/pdfs/           # original PDFs stored by internal document UUID
  library/manifest.json  # PDF metadata and active generation pointer
  index/generations/      # complete immutable hybrid retrieval generations
```

History preserves decoded UTF-8 message text exactly; incomplete assistant output
is labeled `completed:false`. Appends flush/fsync before acknowledgement. Compaction
will never rewrite raw history. Chat deletion tombstones metadata first and
explicitly rewrites only that chat's archive records; other chat record bytes are
preserved. A crash between tombstone and collection resumes cleanup on next startup.
Backups made before deletion can still contain deleted content.

Snapshots publish through temporary writes and atomic rename with a previous
`.bak` copy. An incomplete JSONL suffix is quarantined as `.partial-<id>` before
repair; corrupt complete records or incompatible snapshots fail visibly. Do not
remove the bad original or overwrite it with an empty file. Stop the app, preserve
the data directory, and restore a known-good compatible backup before restarting.
Snapshots/indexes are supporting local files, not a hosted database.
See [`docs/conversation-memory.md`](docs/conversation-memory.md) for checkpoint
recursion, emergency budget recovery, crash behavior and retry details.

## Privacy and security

Only active PDFs are factual authority for document answers. History and summaries
provide conversational context, never replacement evidence. Parsing, chunking,
embeddings, indexing and retrieval happen locally. The selected remote provider may
see the question, selected snippets, instructions, and necessary conversation
context. Entire PDFs are not uploaded.

Local history is intentionally verbatim and may contain sensitive text you paste;
the application does not encrypt local files. Operational logs are separate and
redact likely credentials. Provider credentials remain in session memory by default,
with explicit OS-vault opt-in for persistence. Do not enter keys into chats,
environment files or repository files. No analytics or telemetry is enabled. Use OS
account and disk protection for local files/backups.

See [`docs/provider-capabilities.md`](docs/provider-capabilities.md) for the
provider-specific wire protocols, exact data boundary, credential lifecycle, and
current unverified capability status.
See [`docs/streaming-contract.md`](docs/streaming-contract.md) for the POST/SSE
events, error handling, cancellation, retry, and citation contracts.
The live end-to-end smoke prerequisites and environment variables are documented in
[`docs/e2e.md`](docs/e2e.md); it remains unexecuted.

The composer warns when text resembles a common API key or bearer token. This is a
heuristic warning, not a blocker: if sent, the text is saved verbatim and may be
included in the selected provider request. Remove unintended secrets before sending.

### Export, deletion, and recovery

Use the download controls beside a chat to export it as Markdown or JSON. The
Markdown format places each message in a dynamically sized code fence so message
content cannot escape into active Markdown. Both formats preserve Unicode and mark
incomplete assistant attempts. The Settings page can download a coherent raw
`chat_history.jsonl` snapshot. Each download asks for confirmation because exports
contain verbatim history and can include sensitive text. The backup includes raw
message records; it does not include PDFs or configured credential stores. Any
secret a user pasted into a message remains in the verbatim history export.

Deleting a chat requires confirmation, tombstones its metadata, and removes only
that chat's records from the active history. A pre-deletion backup can still contain
those records. Removing a PDF makes it unavailable to future retrieval while
historical citations remain unchanged and may no longer open. The original PDF and
index generations live under `data/library/` and `data/index/`; deleting the PDF
does not delete conversation history.

If storage or an index becomes corrupt, stop the app and preserve the complete
`data/` directory before recovery. Restore a known-good backup or rebuild the local
index from original PDFs when possible. Do not replace a corrupt state file with an
empty one. Raw history exports are plain UTF-8 JSONL and can contain private text;
store them with the same care as the application's data directory.

### Keyboard, language, and theme controls

- Press **Enter** to send; press **Shift+Enter** to insert a newline. The composer
  grows with its content up to its display limit.
- While mobile navigation is open, press **Escape** to close it. The source panel
  also closes with **Escape**; focus returns to the control that opened it.
- Use the header language selector for English, French, or Persian. Persian switches
  the interface to right-to-left layout; mixed-script messages use automatic text
  direction. Use the adjacent theme control to switch light/dark appearance.
- The selected language and theme are stored as non-sensitive browser preferences.
  Provider credentials and canonical conversation history are not stored in browser
  local storage.

## Remaining implementation slices and limitations

Provider/settings, grounded streaming/citations, recursive memory/context recovery,
exports, and core responsive/localization behavior are written but unverified.
Remaining work includes full release checks and measured retrieval/capability
documentation. Optional local OCR, multilingual
reranking and bounded Library retrieval tools are implemented but unverified. An
optional OpenAI Responses-compatible endpoint can be configured in Settings; HTTPS
is required except for loopback HTTP, and endpoint tool/usage capabilities are checked
explicitly. Do not assume that every OpenAI-compatible service supports Responses.
Local embeddings default to `intfloat/multilingual-e5-small`; E5 query/document
prefixes and consistent normalization are required. Changing embedding models
will require a complete safe index rebuild. Optional local OCR requires Tesseract
and the configured language packs. No integration is claimed verified until
manual checks are complete. See `docs/library.md` for downloads, storage, PDF/OCR
limitations, retrieval evaluation and recovery.

Task progress is in
`openspec/changes/initial-project-documentation/tasks.md`. Checked coding tasks
mean code was written; unchecked `V...` tasks mean execution and verification
remain for the user. The complete product is not release-ready.

