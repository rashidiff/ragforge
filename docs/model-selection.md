# Provider configuration and chat model selection

Select the provider and save its key in **Settings**. Select the model from the
**LLM model** dropdown in the chat header. The selection is persisted in the
existing non-secret settings store and applies to subsequent requests across the
workspace. Switching models does not rewrite chat history, summaries, PDFs, or
indexes. Changing provider selects its own default instead of retaining a model
identifier from the previous provider. Previously saved model IDs remain visible.

Model changes are blocked while an answer is running. Sending/retrying is disabled
while the model selection is being saved. A failed save retains the previous
selection, reports an error, and allows retry. A stale provider selection returns
409 rather than changing another provider's settings.

## Reviewed documentation catalogs

Reviewed **2026-11-12**. These are curated text-generation suggestions from official
documentation, not a live account entitlement list. Availability, billing, regional
restrictions, and model lifecycle are controlled by each provider. Catalog loading
uses no credentials and performs no remote request or generation. The existing
connection test uses the selected model, or the provider default when unset, and
may make a billable provider request when the user explicitly requests it.

| Provider | Suggested models | Default |
| --- | --- | --- |
| OpenAI | GPT-4.1 / mini / nano; GPT-6.1 Sol / Terra; GPT-6 Astra / Luna | `gpt-4.1` |
| Anthropic | Claude Sonnet 5.5, Opus 5.5, Haiku 5.5, Fable 5.2 | `claude-sonnet-5-5` |
| Google Gemini | Gemini 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite, 4 Carbon, 4 Argon | `gemini-3.8-flash` |
| OpenAI-compatible | Deployment-specific; use **Other model…** in the chat menu | None |

Official sources:

- [OpenAI model catalog](https://developers.openai.com/api/docs/models) and
  [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1),
  [mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
  [nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano).
- [Anthropic models](https://platform.claude.com/docs/en/models/overview).
- [Google Gemini models](https://ai.google.dev/gemini-api/docs/models).

Audio-only, image-generation-only, embedding, and restricted specialized models are
not included. Use **Other model…** for a supported snapshot or deployment ID not in
the suggestions. Compatible endpoints must implement OpenAI Responses; no universal
model list exists for arbitrary endpoints. Neither a catalog entry nor accepting a
custom ID guarantees access or compatibility. Provider errors remain visible.

Configured context/output budgets are retained when changing a model; the dropdown
does not automatically increase token budgets or prices. Advanced limits remain
in Settings. Compatibility is covered by mocked protocol tests; this catalog review
does not claim live credentials were used to test every listed model.

## API

- `GET /api/settings/models`: active provider, saved/default model IDs, model options,
  official source URL, and review date. No key is included.
- `PUT /api/settings/model`: `{provider, model}`; validates nonblank bounded IDs,
  checks the provider has not changed, and returns the public settings contract.
- Existing `GET/PUT /api/settings` remains backward compatible for integrations.

## Interface languages

English and French remain selectable. A stored `fa` interface preference migrates
to English; no history or document data is changed. Persian and other Unicode text
remain supported inside PDFs, questions, answers, exports, and mixed-direction text.
The original requirements baseline is retained as historical source; the interface
locale change was explicitly requested after that baseline was approved.
