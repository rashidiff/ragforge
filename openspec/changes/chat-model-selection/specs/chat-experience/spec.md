## ADDED Requirements

### Requirement: Chat header model menu
The chat header SHALL offer documented text-model suggestions for the configured
provider, preserve saved IDs, and allow explicit custom deployment IDs. Settings
SHALL configure the provider and credentials without a model-name field.

#### Scenario: Provider configuration and next-turn model selection
- **WHEN** a provider is saved and a model is selected from the chat header
- **THEN** subsequent requests use that saved model, other providers do not inherit
  an incompatible old model ID, and archived messages/PDFs/indexes remain intact.

#### Scenario: Model save failure or active generation
- **WHEN** a save fails, the configured provider changed, or generation is active
- **THEN** errors are visible, stale/active changes are rejected, and the previous
  selection is retained; sending is blocked during the save.

### Requirement: Honest documented catalogs
Catalogs SHALL identify their official source and review date and SHALL not imply
account-specific access or live-tested compatibility. Loading the catalog SHALL
make no paid provider call or disclose credentials.

#### Scenario: Custom endpoint
- **WHEN** the provider is an arbitrary OpenAI-compatible endpoint
- **THEN** its saved model remains available and custom IDs can be entered in the
  chat menu without inventing an endpoint-independent list.

## MODIFIED Requirements

### Requirement: Multilingual accessibility
The interface SHALL support English and French with keyboard navigation, responsive
layout and themes. Unicode and mixed-direction document/message text SHALL remain
supported, including Persian content.

#### Scenario: Removed locale preference
- **WHEN** the browser has a stored Persian interface preference
- **THEN** the interface falls back to English without altering any chat or PDF.
