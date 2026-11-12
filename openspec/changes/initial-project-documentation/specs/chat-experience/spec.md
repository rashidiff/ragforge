# Spec Delta

## Purpose

Provide an accessible multilingual interface for independent conversations grounded in the shared local PDF Library.

## ADDED Requirements

### Requirement: Independent chat management
The system SHALL provide new chats, automatic titles, rename, confirmed deletion, and a chronological chat list.

#### Scenario: Independent chat management acceptance
- **WHEN** a user creates two chats, renames one, and confirms deletion of the other
- **THEN** each has independent messages and memory; only the selected chat disappears.

### Requirement: Responsive navigation
The system SHALL provide a collapsible sidebar with New Chat, Library, and Settings alongside a central conversation panel without signup or profile screens.

#### Scenario: Responsive navigation acceptance
- **WHEN** the interface is used on desktop or mobile
- **THEN** all three destinations remain reachable, with loading, empty-library onboarding, missing-key warnings, clear errors, and visible focus.

### Requirement: Composer and answer controls
The system SHALL support distinct message bubbles, sanitized Markdown/code, an autoresizing multiline composer, Enter to send, Shift+Enter for newline, send/stop, retry last answer, copy, and error dismissal.

#### Scenario: Composer and answer controls acceptance
- **WHEN** a user sends, stops, retries, copies, or scrolls away from the newest content
- **THEN** controls behave as labeled; retry is a distinct attempt; auto-scroll does not pull the user away from older content.

### Requirement: Multilingual accessibility
The system SHALL support Unicode and Persian RTL, French, and English throughout input, extraction, search, and answers, with keyboard navigation, responsive layout, and light/dark themes.

#### Scenario: Multilingual accessibility acceptance
- **WHEN** a user types mixed Persian and Latin text and asks in French
- **THEN** text remains intact, directionality and focus are usable, answers follow the user language, and long messages remain readable.

### Requirement: Source inspection
The system SHALL display inline filename/page citations and a source drawer with retrieved snippets and exact PDF-page preview.

#### Scenario: Source inspection acceptance
- **WHEN** a user opens a supported citation or a historical citation to a deleted document
- **THEN** the exact source/page opens for available sources; deleted sources are marked unavailable without rewriting history.

### Requirement: Truthful progress
The system SHALL show event-driven request, upload, and compaction states without invented thinking or private chain of thought.

#### Scenario: Truthful progress acceptance
- **WHEN** retrieval, optional reranking, provider call, streaming, saving, indexing, or compaction runs
- **THEN** only real stages appear; upload stages cover validation/extraction/optional OCR/chunking/embedding/indexing/ready or failed; compaction failure and retry are visible.

