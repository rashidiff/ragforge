# Provider boundaries and capability status

This document describes the implemented provider protocols and records what has
not yet been verified. Provider behavior is not considered tested until the
provider-specific protocol fixtures and any available live smoke are run and
their results are recorded. The repository's automated tests are authored but
have not been executed.

## Data sent to a selected provider

PDF parsing, OCR, embeddings, indexing, retrieval, reranking, and citation checks
run locally. A generation request can send the canonical system instructions,
the current question, the necessary conversation summary/tail, and only the
bounded excerpts retrieved for that request. The complete PDF and local index are
not uploaded. Optional retrieval tools can request additional excerpts from the
same local Library, within the configured tool-round limit. Compaction sends the
selected conversation batch and previous summary to the configured model. Provider
calls and first-time package/model downloads require network access.

## Implemented protocol surface

| Setting | Protocol implemented in code | Streaming/tool/usage behavior | Verification status |
|---|---|---|---|
| OpenAI | Responses API | Streamed text and terminal events; the two restricted Library tools; usage when returned by the response | Unverified; protocol tests authored, not run; live credentials/smoke not recorded |
| Anthropic | Messages API | Provider-specific message/system mapping, streamed events, restricted Library tools, and usage when reported | Unverified; protocol tests authored, not run; live credentials/smoke not recorded |
| Google Gemini | `streamGenerateContent` / `generateContent` | Provider-specific contents/function mapping, streamed candidates, and usage when `usageMetadata` is returned | Unverified; protocol tests authored, not run; live credentials/smoke not recorded |
| OpenAI-compatible | Configured OpenAI Responses-compatible `/responses` endpoint | HTTPS required except loopback HTTP; tool schema is configured explicitly and can fall back when rejected; usage is reported only when observed | Unverified for each endpoint; compatibility with arbitrary chat-completion APIs is not claimed |

The connection test checks a small non-streamed provider request. It does not prove
that a future streamed request, a particular tool call, or every model limit will
work. Model context/output limits remain explicit application settings. Do not
interpret a configured capability or authored fake-response test as a successful
live provider test. Unsupported optional tool behavior must be reported or fall
back to the deterministic initial local retrieval path; it must not expand the
model's tool surface.

## Credential lifecycle

Provider keys are write-only settings. They remain in backend session memory by
default and are never returned by the API or placed in browser storage. Persistence
is opt-in and uses the operating-system credential vault; a missing/unavailable
vault is an error and has no plaintext-file fallback. Removing a key clears the
selected provider credential. Routine activity logs redact likely credential
patterns and do not store full source chunks or secret-bearing prompts. Chat history
is intentionally verbatim, so a key pasted into a message remains in local history
and may be sent as conversation context; the UI warns before sending likely secret
patterns but does not mutate or block the text.

See [the Library guide](library.md) for local model and package downloads, and the
[Privacy and Security section](../README.md#privacy-and-security) for storage and
export handling. No provider path is represented as release-verified until its
unchecked OpenSpec verification task has been completed with evidence.
