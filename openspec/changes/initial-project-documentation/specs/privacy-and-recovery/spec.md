# Spec Delta

## Purpose

Protect local data and credentials while making operational activity durable, recoverable, and transparent to the user.

## ADDED Requirements

### Requirement: Explicit data boundary
The system SHALL keep PDFs, extraction, embeddings, indexes, retrieval, and supporting state local and disclose that selected snippets and needed conversational context are sent to the configured remote provider.

#### Scenario: Explicit data boundary acceptance
- **WHEN** a user views Settings or documentation
- **THEN** storage paths, remote-API and initial-download requirements are explicit; there is no telemetry or analytics without opt-in.

### Requirement: Session-default secret handling
The system SHALL keep keys in session memory by default, mask entry, return only key availability, and persist keys solely in an OS vault after explicit opt-in.

#### Scenario: Session-default secret handling acceptance
- **WHEN** a key is entered, saved, removed, logged, or accidentally pasted into chat
- **THEN** settings and routine logs never disclose keys/headers/tokens; browser/repository/plaintext settings never store keys; pasted chat secrets trigger a warning while verbatim local history is retained.

### Requirement: Separate durable activity log
The system SHALL append operational events to data/system.log.jsonl separately from raw history, including timezone timestamps, severity, type, relevant IDs, redacted user requests, retrieval IDs/pages/scores, durations, errors, provider/model, and available usage/cost/status.

#### Scenario: Separate durable activity log acceptance
- **WHEN** retrieval, indexing, compaction, provider calls, or failures occur
- **THEN** correlated start/end/status events are durable; full chunks require explicit local debug opt-in; credential patterns and secret-bearing prompts remain excluded from routine logs. Persist user-submitted text in the canonical history; the activity log records it only after credential-pattern redaction.

### Requirement: Safe writes and recovery
The system SHALL lock shared writes, persist user content before generation, persist complete assistant content only on success, append a separate durable activity log, and atomically publish state.

#### Scenario: Safe writes and recovery acceptance
- **WHEN** a process crashes during append, compaction, deletion, or rebuild
- **THEN** valid complete records recover safely, incomplete output stays incomplete, corruption and persistence failures are surfaced with safe retry/recovery guidance, and no unrelated chat, document, or known-good state is silently lost; provider failure handling follows the request lifecycle and does not silently report an unlogged success.

### Requirement: Local attack-surface limits
The system SHALL use loopback binding, tight CORS origins, bounded request concurrency, validated PDF content, managed file serving, and no privileged tools for document instructions.

#### Scenario: Local attack-surface limits acceptance
- **WHEN** a malicious origin, filename, PDF instruction, or repeated concurrent request is submitted
- **THEN** access and resource use remain constrained; no command execution, credential access, arbitrary filesystem serving, or unauthorized external retrieval results.

### Requirement: Deletion and snapshot consistency
The system SHALL isolate explicit chat deletion from other chats and exclude a removed PDF from subsequent retrieval while preserving historical citations as unavailable.

#### Scenario: Deletion and snapshot consistency acceptance
- **WHEN** a selected chat or PDF is deleted while an operation is active
- **THEN** chat tombstones and deliberate garbage collection affect only that chat; deleted PDFs cannot supply future evidence and historical citation references remain unchanged but indicate unavailability.

### Requirement: Portable local exports
The planned system SHALL provide the recommended local Markdown/JSON chat export and raw-history backup through safe download endpoints.

#### Scenario: Portable local exports acceptance
- **WHEN** a user exports a chat or makes an archive backup
- **THEN** complete authorized local history is downloadable without directory traversal or secret-store exposure; users are warned that verbatim history can contain pasted sensitive text.

