# GitHub Actions CI

The repository CI workflow is `.github/workflows/ci.yml`. GitHub Actions starts
it on every push and pull request. The workflow runs on `ubuntu-latest` with
Python 3.11 and Node.js 22; each job has a timeout, dependency caching, and
fail-fast steps. A failed install, test, formatter, linter, type check, or
frontend build fails its job. No provider secrets are configured or needed.

The backend job installs `backend[dev,ci]`, which includes the local PDF and
vector-index libraries without downloading or initializing a sentence-transformer
model. It runs all `backend/tests` with pytest, Ruff lint and formatting checks,
and mypy over `backend/app`. Provider protocol tests use HTTPX mock transports;
application generation and compaction tests inject fake adapters. The explicit
offline pipeline integration in `backend/tests/test_ci_integration.py` writes to
pytest's per-test temporary directory and covers PDF ingestion, local hybrid
retrieval, mocked grounded streaming, durable conversation records, redacted
activity logs, and recursive compaction without changing `data/`.

The complete backend suite also exercises PDF-specific behavior in
`test_pdf_ingestion.py`, `test_pdf_extraction.py`, and `test_library_api.py`;
history and logging in `test_history_logging.py` and `test_chat_store.py`; and
compaction/checkpoint recovery in `test_compaction.py` and `test_compaction_api.py`.
All test fixtures use pytest `tmp_path` or in-memory fakes for runtime state.

The frontend job installs `frontend` dependencies and runs Vitest component and
library tests, a Chromium Playwright browser integration using mocked HTTP/SSE
responses, ESLint over source, tests, and Playwright configurations, Prettier's
check mode, the TypeScript project type check, and
the production Vite build. npm downloads are cached using the package manifest
hash. The separate live-provider Playwright flow remains an explicitly configured
release check because it requires real local PDFs, an index, and provider credentials.

## Workflow badge

After the repository is hosted on GitHub, replace `OWNER/REPOSITORY` in the
README badge URL with its GitHub owner and repository name. The project has not
been pushed or connected to a GitHub repository, so no live status URL is known
yet. A badge image only reports the latest Actions run; it is not evidence that a
workflow has passed until GitHub has run it.
