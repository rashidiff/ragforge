# Spec Delta

## Purpose

Separate permanent complete conversation history from bounded, recoverable model-visible recursive memory for each chat.

## ADDED Requirements

### Requirement: Canonical verbatim archive
The system SHALL retain every complete user and assistant message verbatim and indefinitely in data/chat_history.jsonl unless the user explicitly deletes that chat. Compaction SHALL NOT rewrite, truncate, or replace archive messages.

#### Scenario: Canonical verbatim archive acceptance
- **WHEN** Unicode messages are saved and repeatedly compacted
- **THEN** decoded message content and stable chronological ordering remain identical; complete records carry event/chat/message/request IDs, role, content, created_at, completed:true, and metadata.

### Requirement: Per-chat eight-message recursion
The system SHALL compact the next eight uncompacted complete conversational messages per chat with the previous cumulative summary, counting saved users and finalized assistants only.

#### Scenario: Per-chat eight-message recursion acceptance
- **WHEN** one chat reaches 8, 16, and 24 completed messages while another chat has fewer than eight
- **THEN** S1 uses empty plus 1-8, S2 uses S1 plus 9-16, and S3 uses S2 plus 17-24; deltas, tools, statuses, incomplete answers, and other chats do not increment that counter.

### Requirement: Atomic compaction checkpoint
The system SHALL separately persist summary, last_compacted_message_id, monotonic compacted count, prompt_version, summary_revision, and timestamps only after successful validated compaction.

#### Scenario: Atomic compaction checkpoint acceptance
- **WHEN** compaction fails, restarts, or races a repeated attempt
- **THEN** old summary and full tail remain usable; retries are idempotent; restart resumes deterministic history boundaries without skipping or double-counting messages.

### Requirement: Structured memory with source pointers
The system SHALL retain enduring entities, selected documents, unresolved questions, stated preferences, decisions, constraints, uncertainty, contradictions, and source pointers in bounded structured summaries without credentials or invented evidence.

#### Scenario: Structured memory with source pointers acceptance
- **WHEN** old summary and the next batch exceed the configured summary target
- **THEN** recursive rewriting targets approximately 500-900 tokens, drops redundancy with reasons for important constraint loss, and re-retrieves actual PDF passages for factual claims.

### Requirement: Bounded context without duplicate intent
The system SHALL load persisted memory and only complete post-checkpoint messages, include the current question exactly once, and enforce provider/model-aware total input and output budgets.

#### Scenario: Bounded context without duplicate intent acceptance
- **WHEN** the threshold is hit mid-turn or an individual question is unusually long
- **THEN** compaction does not unnecessarily block answering; older eligible messages can be emergency-compacted, retrieval and summary stay bounded, recent intent survives, and an unfit question gets a clear error rather than silent truncation.

