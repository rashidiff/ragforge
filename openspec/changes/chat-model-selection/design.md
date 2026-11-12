# Design

Use a server-owned reviewed model catalog and two typed settings routes. Reuse the
existing atomic settings store and provider adapters. The chat header component
loads model suggestions without provider credentials, persists selection through
the backend, and disables sending during a save. Configuration changes share the
generation registry lock with lease acquisition to prevent changing an in-flight
request's provider/model. Custom endpoints use explicit deployment IDs in the chat
menu; no endpoint guessing or background remote discovery is introduced.

Remove the Persian locale dictionary/option and migrate its saved browser preference
to English. English/French remain. Preserve auto text direction and all archived
Unicode data. The original approved baseline remains historical source; these user
instructions supersede its Persian-interface requirement only.
