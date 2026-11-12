# Tasks

- [x] Add reviewed, sourced provider model catalogs and typed API contracts.
- [x] Add persistent chat model selection and active/stale-provider guards.
- [x] Move model selection from Settings to an accessible responsive chat menu.
- [x] Preserve explicit saved/custom model IDs without exposing credentials.
- [x] Remove Persian interface and migrate saved locale to English; preserve Unicode data.
- [x] Author backend, component, and mocked-browser regression coverage.
- [x] Update product documentation and specifications for the approved scope.
- [x] Execute hosted CI and record results without running local checks.

Evidence: https://github.com/rashidiff/ragforge/actions/runs/43268633628
Commit: d633e902fcbb55b8791bb83c97d5e0ffdf6c882e
Backend tests/static checks, frontend tests/browser/lint/typecheck/build, and Windows index regression all passed on hosted runners. No live-provider entitlement claims are made.
