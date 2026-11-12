# Spec Delta

## Purpose

Generate streamed, cited answers using only local PDF evidence and explicitly configured remote language models.

## ADDED Requirements

### Requirement: PDF-only factual grounding
The system SHALL use only active Library PDFs as factual authority for collection questions; prior conversation and summaries SHALL provide context only.

#### Scenario: PDF-only factual grounding acceptance
- **WHEN** evidence is absent, contradictory, spans several PDFs, or the Library is empty
- **THEN** answers acknowledge missing evidence or conflicts, cite all relevant available sides, or request PDF upload; no web search or unsupported pretrained facts supply missing evidence.

### Requirement: Coreference-aware hybrid retrieval
The system SHALL construct retrieval queries using the independent chat memory and recent complete tail, combine local semantic and lexical candidates, deduplicate, and select token-bounded snippets with provenance.

#### Scenario: Coreference-aware hybrid retrieval acceptance
- **WHEN** a follow-up refers to an earlier entity or exact identifier
- **THEN** relevant snippets are retrieved from current documents; optional reranking remains local; score thresholds are evaluated on test queries rather than presented as universal confidence.

### Requirement: Bounded library tools
The system SHALL expose backend search_library and get_source_excerpt operations, perform deterministic initial retrieval, and allow at most two optional additional retrieval rounds for tool-capable models.

#### Scenario: Bounded library tools acceptance
- **WHEN** a model requests missing evidence or lacks tool support
- **THEN** supported requests search only the Library with actual round statuses; unsupported models still work through backend retrieval; no shell, filesystem, web, or external network tool is granted.

### Requirement: Provider and model configuration
The system SHALL support provider-specific OpenAI, Anthropic, and Google Gemini adapters, with optional OpenAI-compatible endpoints, editable model settings, masked key entry, connection testing, and explicit capability validation.

#### Scenario: Provider and model configuration acceptance
- **WHEN** a user selects a model, supplies a key, and tests it
- **THEN** the correct provider protocol is used; unsupported models, missing/invalid keys, rate limits, outages, and timeouts yield clear errors and retry guidance without simulated success.

### Requirement: Canonical model input
The system SHALL send one canonical system prompt, clearly labeled persisted memory if present, completed uncompacted conversation in order, delimited untrusted retrieved excerpts with source IDs/names/pages, and the current user question exactly once.

#### Scenario: Canonical model input acceptance
- **WHEN** any answer request is constructed
- **THEN** provider roles preserve this logical structure; tool schemas travel through tool APIs or backend orchestration; secrets and full PDFs are not included.

### Requirement: True streaming and validated citations
The system SHALL forward real upstream text deltas, validate citations against this request and currently accessible documents, persist exact completed answer text, and expose cancellation.

#### Scenario: True streaming and validated citations acceptance
- **WHEN** generation succeeds, fails, or is canceled
- **THEN** near-claim citations open exact sources; completion includes duration and available usage; interruption is explicit and never falsely complete; upstream work is aborted where supported.

### Requirement: Document injection isolation
The system SHALL treat extracted PDF content as untrusted data that cannot override canonical instructions, access credentials, change settings, or execute commands.

#### Scenario: Document injection isolation acceptance
- **WHEN** a retrieved passage contains fake system instructions or secret-exfiltration requests
- **THEN** the passage remains fenced source content and no privileged action or secret disclosure follows.

