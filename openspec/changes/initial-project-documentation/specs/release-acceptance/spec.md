# Spec Delta

## Purpose

Define verifiable project completion and incremental release gates without mistaking planning or mocked behavior for a working product.

## ADDED Requirements

### Requirement: Complete acceptance coverage
The delivered application SHALL satisfy the twelve numbered acceptance criteria and definition of done from `agent.md` sections 10-11, retained verbatim in `requirements-baseline.md`; each criterion SHALL have a recorded result and evidence artifact or command output.

#### Scenario: Complete acceptance coverage acceptance
- **WHEN** release readiness is assessed
- **THEN** the release record contains one pass/fail/unverified result for each criterion: (1) no-login localhost launch without Docker/database; (2) normal PDF upload, progress, grounded answer and clickable page citation; (3) unsupported, multi-PDF and contradiction queries; (4) malformed/non-PDF rejection and image-only OCR offer or warning; (5) provider/model/key test with key absent from settings response/logs/repository; (6) real status transitions, incremental upstream tokens and cancellation without false completion; (7) same-chat 8/16/24 recursion, exact preserved history, independent chat, restart and failed compaction; (8) one current question and the required system/memory/tail/snippets, with long-input budget fallback; (9) deletion exclusion, preserved chats, reindex and restart; (10) PDF injection isolation and no secret leak; (11) desktop/mobile, keyboard, long answers, RTL Persian, mixed French/English, citations, themes and errors; (12) automated suite, formatters, type checks and real end-to-end smoke. Any unverified item blocks a completion claim and is reported with reason and evidence.

### Requirement: Layered verification
The project SHALL include backend tests, frontend component tests, a browser smoke test, formatting, type checks, and testable failure/recovery fixtures mapped to their capability requirement IDs.

#### Scenario: Layered verification acceptance
- **WHEN** an independently implementable phase is completed
- **THEN** its task group identifies requirement IDs and test evidence, and its tests and documentation ship with it; provider protocol fakes validate deterministic cases but do not replace a true end-to-end smoke using real local PDF indexing and a configured live provider.

### Requirement: GitHub-hosted continuous integration
The repository SHALL provide a GitHub Actions workflow that runs on every push and pull request and fails when any required automated test, lint, formatting, type-check, or production frontend build step fails. CI SHALL provision the declared Python and Node.js environments, install backend and frontend dependencies, use dependency caches and bounded job timeouts, and run without paid LLM calls, real provider credentials, or production data.

#### Scenario: Push and pull request checks
- **WHEN** a commit is pushed or a pull request is opened or updated
- **THEN** GitHub Actions runs the backend pytest suite, backend lint/format/type checks, frontend component and mocked browser integration tests, frontend lint/format/type checks, and frontend production build; any unsuccessful required command fails its job and the workflow does not report success.

#### Scenario: Offline isolated integration coverage
- **WHEN** backend CI integration cases run
- **THEN** PDF ingestion and local RAG retrieval, provider streaming, conversation history, activity logging, and recursive compaction are exercised using temporary storage and mocked/fake external LLM adapters; no real API key or network provider request is required.

#### Scenario: CI status is not presumed
- **WHEN** workflow files and CI tests have been authored but GitHub Actions has not run them
- **THEN** implementation tasks may be recorded complete, while execution and release-verification tasks remain unchecked and the README describes the workflow as configured but not yet verified.

### Requirement: Honest support report
The release SHALL report pass/fail evidence, prerequisites, unsupported provider or OCR conditions, tested dependency compatibility, and repeatable installation commands.

#### Scenario: Honest support report acceptance
- **WHEN** a provider, operating system, OCR language, or vector fallback has not been exercised
- **THEN** the report identifies it as unverified or unsupported rather than claiming success; references are consulted at integration time and versions are pinned after compatibility testing.

### Requirement: Modular phased delivery
The project SHALL follow independently verifiable vertical slices with explicit dependencies and completion gates rather than TODO-only implementations or mocked success paths.

#### Scenario: Modular phased delivery acceptance
- **WHEN** a phase is proposed for completion
- **THEN** the delivered slice runs locally, its specific verification passes, and later optional features do not conceal missing required baseline behavior.

