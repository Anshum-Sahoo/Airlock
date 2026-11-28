# Implementation status

## Backend MVP complete
- [x] Frozen v1.2.1 contracts loaded and validated before startup.
- [x] Production and metadata SQLite initialization; seed 500 demo invoices when production is empty.
- [x] Separate agent/reviewer bearer authorization and exact Origin checks on reviewer mutations.
- [x] Session creation with independent speculative database snapshots.
- [x] Contract session reads, invoice tools, redacted mutation manifests, and deterministic policy evaluation.
- [x] Completion, reviewer rollback, conflict-checked commit, same-transaction receipt, and startup recovery.
- [x] Guarded demo reset and backend security/lifecycle tests.

## Remaining workstreams
- [ ] Next.js dashboard.
- [ ] Nemotron agent runner.

The backend remains a single-process, loopback demo MVP as described in `contracts/API_CONTRACT.md`.
