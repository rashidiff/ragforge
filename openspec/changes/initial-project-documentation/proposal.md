# Proposal

## Why

Local RAG Chat has a comprehensive source requirement document but no capability specifications, architecture decisions, contracts, or implementation checkpoints. Establishing a reviewable baseline before coding will keep the complete project aligned with `agent.md`, especially its grounding, privacy, durability, and recursive-memory constraints.

## What Changes

- Establish the initial intended product behavior as eight new capability specifications; these describe future behavior, not existing functionality.
- Preserve all source requirements in a section-addressable baseline with traceability to specifications, design decisions, roadmap phases, and acceptance tests.
- Define frontend/backend boundaries, local PDF/RAG processing, provider adaptation, durable records, recursive compaction, API schemas, and failure recovery.
- Define independently deliverable implementation phases and test gates. The initial proposal was documentation-only; subsequent approved apply work implemented the application and this GitHub Actions CI gate without generating runtime data.
- Add a GitHub Actions delivery gate with isolated mocked integration tests and backend/frontend automated checks on every push and pull request, without real provider credentials.

## Capabilities

### New Capabilities

- `chat-experience`: Independent chats, responsive multilingual interface, citations, and real operational status.
- `local-runtime`: Local execution, configuration, editable prompts, technology constraints, and distribution.
- `pdf-library`: Safe PDF ingestion, local indexing, library lifecycle, preview, and progress.
- `grounded-generation`: Hybrid retrieval, provider/model integration, streamed grounded answers, and bounded tool retrieval.
- `conversation-memory`: Durable verbatim history and independent per-chat recursive compaction.
- `local-api`: Typed HTTP contracts, streaming events, cancellation, and safe errors.
- `privacy-and-recovery`: Secret handling, structured logs, trust boundaries, atomic persistence, and recovery.
- `release-acceptance`: Automated and real end-to-end verification, platform instructions, and evidence of completion.

### Modified Capabilities

None. The OpenSpec specification inventory is empty.

## Impact

The initial planning step authored OpenSpec artifacts only. Subsequent approved apply work implemented the source layout specified in `agent.md` section 7, React/TypeScript/Vite frontend, Python/FastAPI backend, local multilingual embedding and hybrid indexes, provider adapters, and GitHub Actions CI. No migration, local test/build execution, or real provider call is part of the CI authoring work. See `requirements-baseline.md` for the complete source snapshot and row-level source → capability requirement → acceptance scenario → phase/task map; `design.md` for contracts and decisions; `tasks.md` for implementation and pending execution gates.
