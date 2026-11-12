# Live local-PDF/provider end-to-end smoke

`frontend/e2e/live-rag.e2e.ts` is a real-browser acceptance scenario. It does not
mock the API or provider. It uploads a supplied PDF into the running local Library,
checks a provider-grounded answer and citation drawer, asks a follow-up, stops and
retries a generation, reloads persisted history, then deletes only the chat created
by this test. The uploaded PDF remains in the Library.

## Prepare a disposable local workspace

Install the Playwright package through the normal frontend dependency install, then
install its Chromium browser once with `npx playwright install chromium`. Start the
backend and Vite frontend using the README instructions. Before starting the backend,
set `RAG_DATA_DIR` to a disposable directory so the uploaded test PDF and other local
data do not mix with a personal workspace. Configure and test a real provider/model
and key through Settings; the test reads only the public `has_key`, provider, and
model fields and never accepts a key through its environment.

Supply a PDF whose content supports a question with a stable expected answer
substring. The stop question should take long enough to expose Stop; otherwise the
test reports that stop/retry behavior could not be exercised.

### PowerShell

```powershell
$env:RAG_E2E_PDF_PATH = "C:\path\to\fixture.pdf"
$env:RAG_E2E_QUESTION = "What is the stated deadline?"
$env:RAG_E2E_EXPECTED_ANSWER = "30 days"
$env:RAG_E2E_FOLLOWUP = "Which page gives that deadline?"
$env:RAG_E2E_STOP_QUESTION = "Summarize every section and supporting detail in the document."
$env:RAG_E2E_PROVIDER = "openai"
$env:RAG_E2E_MODEL = "<configured-model>"
cd frontend
npm run test:e2e
```

### POSIX shell

```sh
export RAG_E2E_PDF_PATH="/path/to/fixture.pdf"
export RAG_E2E_QUESTION="What is the stated deadline?"
export RAG_E2E_EXPECTED_ANSWER="30 days"
export RAG_E2E_FOLLOWUP="Which page gives that deadline?"
export RAG_E2E_STOP_QUESTION="Summarize every section and supporting detail in the document."
export RAG_E2E_PROVIDER="openai"
export RAG_E2E_MODEL="<configured-model>"
cd frontend
npm run test:e2e
```

`RAG_E2E_BASE_URL` defaults to `http://127.0.0.1:5173`; set it to the built
FastAPI origin when using production static hosting. `RAG_E2E_PROVIDER` and
`RAG_E2E_MODEL` are optional consistency assertions against current Settings.

The test has not been executed. Record OS, Python/Node/package/browser versions,
PDF fixture identity, provider/model, command, result, and retained trace/evidence
in the release record. A test pass with a live provider is required before claiming
acceptance 2, 3, or 6; the remaining criteria require their own evidence.
