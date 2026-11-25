# Implementation status

## Completed in starter
- [x] Frozen v1.2.1 contracts copied into `contracts/`.
- [x] Environment settings and local-only startup guard.
- [x] Production SQLite invoice table generated from `invoice.schema.json` DDL.
- [x] Production SQLite commit-ledger table initialized to contract DDL.
- [x] Metadata SQLite sessions table initialized to contract DDL.
- [x] Speculative database directory created.
- [x] Required contract JSON files loaded at startup.
- [x] Full contract validator runs before database initialization; invalid contracts abort startup.
- [x] `GET /api/health` implemented against `api.schema.json` HealthResponse.
- [x] Initial health tests added.

## Not implemented yet
- [ ] Seed 500 demo invoices.
- [ ] Agent/reviewer authentication dependencies.
- [ ] Explicit Origin validation middleware/dependency for reviewer mutations.
- [ ] Session creation and per-session speculative DB backup.
- [ ] Tool execution, mutation manifest tracking, policy engine.
- [ ] Completion, reviewer decision, commit, rollback, and recovery orchestration.
- [ ] Demo reset endpoint.
- [ ] Next.js dashboard.
- [ ] Nemotron agent runner.

The checkboxes above describe the starter scaffold only; they do not imply that any unfinished endpoint is available.
