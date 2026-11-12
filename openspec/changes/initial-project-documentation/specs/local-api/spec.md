# Spec Delta

## Purpose

Provide stable typed local HTTP and streaming interfaces with explicit lifecycle, validation, and content safety.

## ADDED Requirements

### Requirement: Health and chat route contracts
The system SHALL implement typed health, chat CRUD, and complete raw-message read routes with the methods and paths specified in `agent.md` section 8.

#### Scenario: Health and chat route success
- **WHEN** a client calls `GET /api/health`, `GET/POST /api/chats`, `PATCH /api/chats/{chat_id}`, `DELETE /api/chats/{chat_id}`, or `GET /api/chats/{chat_id}/messages` with valid input
- **THEN** health returns readiness and warnings; create returns 201 with chat ID/title/timestamps; list is chronological; patch returns the renamed chat; delete returns 204 after durable deletion; history returns the complete stored messages in chronological order.

#### Scenario: Invalid chat route input
- **WHEN** a client submits an empty title, malformed body, or unknown/deleted chat ID
- **THEN** the API returns a safe validation error (422) or not-found (404), without leaking filesystem paths or mutating another chat.

### Requirement: Library and indexing route contracts
The system SHALL implement typed Library upload/list/delete/reindex/PDF and index status/rebuild routes at the methods and paths specified in `agent.md` section 8.

#### Scenario: Library operation lifecycle
- **WHEN** a valid PDF is uploaded, a document is deleted/reindexed, a PDF is previewed, or a full rebuild is requested
- **THEN** upload/reindex/delete/rebuild return a job or document status with a stable job ID; list returns manifest metadata; preview returns only the managed PDF and requested page fragment is interpreted by the client; status reports stage, processed/total when known, errors and active index version.

#### Scenario: Library validation and failure
- **WHEN** upload content is not an acceptable PDF, exceeds the configured limit, a document ID is unknown, or rebuild conflicts with an active mutation
- **THEN** the API returns 415, 413, 404, or 409 respectively; rejected content is not indexed and a failed rebuild does not claim readiness.

### Requirement: Settings route contracts
The system SHALL implement typed settings read/update and provider-connection test routes with write-only credentials.

#### Scenario: Settings read, update and test
- **WHEN** a client calls `GET /api/settings`, `PUT /api/settings`, or `POST /api/settings/test-connection`
- **THEN** reads return provider/model, non-secret options and `has_key`; writes validate changes and return public settings; tests return success/capabilities or a categorized safe failure; no response echoes a key.

#### Scenario: Settings validation
- **WHEN** settings contain mutually exclusive key operations, invalid provider/model limits, or an unsupported value
- **THEN** the API returns 422 with field-level safe details and leaves the previous valid settings active.

### Requirement: Reliable shared contract
The system SHALL maintain a single typed backend request/response/event contract and reliably generate or mirror frontend types with drift checks.

#### Scenario: Reliable shared contract acceptance
- **WHEN** a schema changes or invalid data reaches a route
- **THEN** frontend/backend mismatches fail verification and invalid input is rejected before unsafe side effects; settings reads expose has_key but never a saved key.

### Requirement: Incremental POST event stream
The system SHALL accept JSON chat submissions via fetch POST and return text/event-stream events status, retrieval, token, citation, optional usage, done, and error.

#### Scenario: Incremental POST event stream acceptance
- **WHEN** frames or multibyte UTF-8 characters arrive split across network reads
- **THEN** the client buffers and incrementally decodes correctly, respects blank-line framing and heartbeats, and exposes actual upstream deltas without artificial character delays.

### Requirement: Explicit stream termination
The system SHALL expose stop through request cancellation and distinguish complete, canceled, and failed responses with stable request identity.

#### Scenario: Explicit stream termination acceptance
- **WHEN** the client disconnects, aborts, retries, or encounters an upstream error
- **THEN** the request stops where supported; incomplete content is labeled; retry has a separate attempt; an error cannot masquerade as done with complete:true.

### Requirement: Restricted local content serving
The system SHALL serve only managed PDFs and safe local application assets and sanitize rendered Markdown without untrusted raw HTML.

#### Scenario: Restricted local content serving acceptance
- **WHEN** a caller supplies a traversal path, deleted PDF ID, or malicious model HTML
- **THEN** arbitrary files cannot be read, unavailable PDFs are reported, and no injected script or untrusted innerHTML executes.

