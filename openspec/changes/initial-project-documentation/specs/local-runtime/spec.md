# Spec Delta

## Purpose

Keep the application locally runnable and configurable while preserving explicit network and platform boundaries.

## ADDED Requirements

### Requirement: Local single-user operation
The system SHALL run locally with a Python backend bound to 127.0.0.1 by default, without accounts, required Docker, hosted databases, or cloud infrastructure.

#### Scenario: Local single-user operation acceptance
- **WHEN** the documented launch workflow is followed
- **THEN** the application opens on its configured localhost port without login; remote-provider and initial package/model-download internet requirements are disclosed.

### Requirement: Editable external prompts
The system SHALL load separate versioned UTF-8 answer and compaction Markdown prompts from prompts/system.md and prompts/compaction.md and SHALL NOT use agent.md as an answer prompt.

#### Scenario: Editable external prompts acceptance
- **WHEN** a prompt is replaced, missing, or invalid
- **THEN** replacement requires no code edit; invalid/missing prompts fail clearly rather than silently falling back to embedded large strings.

### Requirement: Local configurable models
The system SHALL use local multilingual embeddings and local dense/lexical retrieval, permit embedding-model changes only with a complete index rebuild, and persist supporting state locally.

#### Scenario: Local configurable models acceptance
- **WHEN** an embedding model changes or the target platform cannot run the default vector implementation
- **THEN** a safe rebuild is required; any substitute is tested, fully local, and documented; no hosted fallback is silently selected.

### Requirement: Installable distribution
The system SHALL provide source, tested locked dependencies, safe example settings, Windows and POSIX launch scripts, and install/start/privacy/architecture/limitations instructions for Windows 11, WSL2, macOS, and Linux.

#### Scenario: Installable distribution acceptance
- **WHEN** a supported platform follows the README
- **THEN** startup succeeds with declared prerequisites; secrets, data, indexes, and environment files are excluded from version control.

