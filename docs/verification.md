# Verification and release acceptance

Automated commands in this checklist are reference commands for GitHub Actions and
are not to be run on the local workstation for this CI setup. The workflow runs the
backend/frontend suites, formatters, linters, type checks, and frontend build on
GitHub-hosted runners. None has been executed by the coding agent; record the
GitHub Actions run URL and results before marking CI verification complete.
Record results, exact dependency versions, operating system, and evidence before
marking a verification task complete. Do not infer a pass from the existence of tests.

## Backend (foundation)

After following README installation, from the repository root:

```sh
.venv/bin/python -m pytest backend/tests
.venv/bin/python -m ruff check backend
.venv/bin/python -m mypy backend/app
```

On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`.
The backend test, lint, formatting, and type commands run in the backend CI job.

## Frontend (foundation)

The checked-in initial model contract was generated from Python annotations
without importing or running application code. To regenerate it after a schema
edit, run `python scripts/generate_contracts.py`. To check drift manually, run
`python scripts/generate_contracts.py --check`; that check has not been run.
For the complete route contract, export OpenAPI and regenerate frontend contracts
only in a GitHub-hosted CI job or a future workflow task. OpenAPI export and
route-type generation have not been executed. The backend contract tests also cover
initial-model drift.

From `frontend/`:

```sh
npm test
npm run typecheck
npm run format:check
npm run build
```

The following are manual release acceptance scenarios and are separate from the
automated CI jobs. Manually open the local UI only when performing product acceptance.
Create two chats; rename one with Persian/French text;
cancel deletion; confirm deletion of only the intended chat; restart and check
the remaining chat. Test keyboard navigation, mobile sidebar, focus in the delete
dialog, API errors, theme controls, and historical incomplete-message labels.
The Library, provider configuration, credential handling and UI are implemented
with authored tests but remain unverified. Manually exercise normal, malformed, duplicate,
scanned and deleted PDFs, real stage polling, reindex/rebuild, restart and failure
recovery. No success should be inferred from the existence of these controls.

## Failure and recovery evidence

The written backend tests cover invalid settings, exact text, concurrent appends,
partial-tail quarantine, complete-line corruption, snapshot publication failures,
chat-deletion isolation and crash recovery, editable prompt failures, chat routes,
origin rejection, safe static paths, PDF validation/deduplication/extraction and
managed preview, embeddings, hybrid search, atomic generation/restart/failure behavior,
and Library UI/jobs. PDF/indexing test fixtures require the optional RAG dependencies; install
`./backend[dev,rag]` before executing those tests. They are unexecuted. Use copies of local
data for failure injection; retain originals and backups for comparison.

Additional unexecuted tests cover provider request/capability contracts, explicit
cancellation, restricted tool names, normalized stream events and raw multipart
body limits. Concrete provider adapters are written; protocol fixtures and live
provider checks still require execution.

## Release status

| Area | Status |
|---|---|
| Windows 11 / WSL2 / macOS / Linux install and launch | Unverified |
| Dependency resolution, compatibility and lockfiles | Pending |
| Backend automated tests, formatting and typing | Not run |
| Frontend automated tests, build, formatting and typing | Not run |
| Browser/keyboard/mobile walkthrough | Not run |
| Full twelve-item source acceptance suite | Not run; an unverified-status matrix is documented |
| Live-provider/PDF end-to-end smoke | Not run; Playwright test code is authored and requires a configured disposable workspace |
| GitHub Actions CI workflow | Configured; pending first GitHub-hosted run |

The full source acceptance criteria are retained in the OpenSpec requirements
baseline. An unverified result is not a successful release check.

## Source acceptance status

All twelve criteria below remain **Unverified**. This records current evidence
status only; it does not claim a pass or replace the required manual and automated
acceptance runs. No tests, installs, builds, formatting, type checks, or browser
walkthroughs were executed during the current implementation work.

| # | Acceptance area | Result | Evidence still needed |
|---|---|---|---|
| 1 | No-login localhost launch without Docker or external database | Unverified | Fresh start on a supported platform and health/UI evidence |
| 2 | PDF upload, indexing progress, grounded answer and clickable page citation | Unverified | Real local PDF plus live-provider browser recording |
| 3 | Absent evidence, multiple PDFs and contradictions | Unverified | Multilingual fixture queries and source-level answer review |
| 4 | Malformed/non-PDF rejection and image-only OCR handling | Unverified | Normal, malformed, encrypted, and scanned fixtures with OCR availability states |
| 5 | Provider/model/key settings and credential exclusion | Unverified | Provider connection, settings/log/repository inspection with test credentials |
| 6 | Real status transitions, streamed deltas and truthful cancellation | Unverified | Live stream, stop, saved-history and incomplete-attempt evidence |
| 7 | Eight-message recursion, 8/16/24 checkpoints, independent chat and restart | Unverified | Two-chat archive/checkpoint comparison after repeated compaction and restart |
| 8 | Canonical provider input, no duplicate question, and context-budget recovery | Unverified | Provider request capture and oversized-question fixtures |
| 9 | PDF deletion exclusion, chat isolation, reindex and restart | Unverified | Deletion/rebuild/restart run with historical citation check |
| 10 | PDF prompt-injection isolation and secret non-disclosure | Unverified | Adversarial PDF fixtures with request, history and log inspection |
| 11 | Desktop/mobile, keyboard, RTL, mixed scripts, citations, themes and errors | Unverified | Accessibility checks and desktop/mobile walkthrough in English, French and Persian |
| 12 | Automated suites, formatting/type checks, and true end-to-end smoke | Unverified | Exact commands, versions, full results and live integration evidence |

OpenSpec tasks V1.1 through V8.5 remain the execution gates. Record command output,
platform/model prerequisites, and retained evidence before changing any result.
