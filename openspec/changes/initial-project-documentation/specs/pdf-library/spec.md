# Spec Delta

## Purpose

Manage safe local PDF ingestion and durable searchable Library state with precise source-page provenance.

## ADDED Requirements

### Requirement: Safe PDF intake
The system SHALL validate PDF extension, signature and readable content, configurable file-size limits, sanitized filenames, and internal document IDs; encrypted, malformed, unsupported, or unreadable inputs SHALL receive clear errors.

#### Scenario: Safe PDF intake acceptance
- **WHEN** a valid PDF, oversized file, traversal filename, or non-PDF is uploaded
- **THEN** only valid permitted PDFs enter the library; the suggested size default is 50 MB; paths cannot escape managed storage.

### Requirement: Library metadata and deduplication
The system SHALL preserve original PDFs locally and expose filename/title, SHA-256, size, pages, import time, status, warnings, index version, and errors; identical content SHALL be reported without duplicate chunks.

#### Scenario: Library metadata and deduplication acceptance
- **WHEN** a PDF is uploaded twice or indexing fails
- **THEN** the duplicate is identified by content hash; failed jobs remain accurately marked and are not advertised as searchable.

### Requirement: Page-aware multilingual extraction
The system SHALL preserve page references, reasonable reading order, important table text where possible, and Unicode during extraction and chunking.

#### Scenario: Page-aware multilingual extraction acceptance
- **WHEN** mixed-language or multi-page documents are indexed
- **THEN** each chunk retains immutable identity, document/name, exact page range, text/hash, position, and embedding version, supporting precise citations.

### Requirement: Explicit local OCR
The system SHALL detect empty or suspiciously sparse extraction and offer optional local OCR with availability/language-pack checks or a clear warning.

#### Scenario: Explicit local OCR acceptance
- **WHEN** an image-only PDF is uploaded with OCR missing or disabled
- **THEN** the application does not pretend the scan is searchable; enabling available OCR exposes actual OCR progress and any remaining limitations.

### Requirement: Persistent local hybrid indexing
The system SHALL batch local embeddings, persist dense and lexical indexes plus chunk metadata and stable vector-to-chunk mapping, and expose indexing progress. A document is ready only when extraction/chunk metadata and both configured retrieval indexes are durably published in one validated generation.

#### Scenario: Persistent local hybrid indexing acceptance
- **WHEN** successful indexing completes and the app restarts
- **THEN** the document is searchable in all chats from the published generation without remote OCR, remote embeddings, cloud vectors, or whole-PDF upload; before publication it remains visibly indexing and is excluded from retrieval.

### Requirement: Safe library lifecycle
The system SHALL support preview, remove, reindex, and full rebuild with atomic index publication and consistent query snapshots.

#### Scenario: Safe library lifecycle acceptance
- **WHEN** deletion, embedding changes, corruption, or rebuild failure occurs during queries
- **THEN** removed documents are excluded from future retrieval; queries never use partial indexes; failure retains the prior known-good generation while immediately filtering deleted documents, or clearly reports Library unavailability when no safe generation exists; status never says ready until the new generation validates, and old raw chats remain intact.

