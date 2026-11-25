# Changelog

## v1.2.1 — Targeted security correction: server-side Origin allowlist (from v1.2.0)

v1.2.1 restores mandatory server-side `Origin` allowlist enforcement on browser-originated state-changing reviewer and demo endpoints without weakening `TrustedHostMiddleware` or bearer-token separation.

### Security requirement restored
1. **Exact `CORS_ORIGINS` allowlist**: Uses `CORS_ORIGINS` (`http://localhost:3000,http://127.0.0.1:3000` by default) with exact `scheme://host[:port]` matching; startup fails if empty or `*`.
2. **Protected endpoints**: Enforced on `POST /api/sessions/{session_id}/commit`, `POST /api/sessions/{session_id}/rollback`, and `POST /api/demo/reset`.
3. **Reject before action**: Missing, empty, `"null"`, malformed, or untrusted `Origin` headers are rejected before bearer-token verification, body parsing, lock acquisition, session lookup, or state mutation.
4. **CORS is not authentication**: `CORSMiddleware` remains browser response policy only; authorization still requires `Authorization: Bearer <AIRLOCK_REVIEWER_TOKEN>`.
5. **No header spoofing trust**: `X-Forwarded-For` / forwarded headers are ignored, allowed origins are never derived from `Host`, and `TrustedHostMiddleware` remains enforced.
6. **Consistent error contract**: Forbidden `Origin` requests return HTTP `403` with `error.code = "FORBIDDEN"` (`error.schema.json`).
7. **Non-browser test clients**: `curl` and test harnesses must explicitly send an allowlisted `Origin` header (e.g., `Origin: http://localhost:3000`) on `commit`, `rollback`, and `reset`.
8. **Role separation preserved**: `AIRLOCK_AGENT_TOKEN` and `AIRLOCK_REVIEWER_TOKEN` remain strictly separated; agent tokens still fail with `401 UNAUTHORIZED_REVIEWER` even with a valid `Origin`.

### Changes by file
- **`contracts/API_CONTRACT.md`**: Updated version to `v1.2.1`; updated Section 3.1 endpoint summary (`rollback` now includes `403`), Sections 3.5–3.6 (server-side `Origin` allowlist, check order, proxy/host header rules, non-browser testing guidance), Section 9 (`FORBIDDEN` description and check order), Sections 10.7–10.9 (`Origin` header, `FORBIDDEN` error code, `403 FORBIDDEN` example), and Section 12 (contract tests 31–34).
- **`contracts/README.md`**: Updated version to `v1.2.1`, endpoint authentication table, local-only security assumptions, non-browser testing note, error-code summary, and validation checklist.
- **`CHANGELOG.md`**: Added `v1.2.1` release notes.
- **`scripts/validate_contracts.py`**: Updated validator version to `v1.2.1` and added cross-file security assertions for server-side `Origin` allowlist enforcement on `commit`, `rollback`, and `reset`.
- **Unchanged**: `api.schema.json`, `error.schema.json` (`FORBIDDEN` → `403` already defined), `manifest.schema.json`, `invoice.schema.json`, `tools.json`, `policies.json`, `examples/*.json`, and `.env.example`.

## v1.2.0 — Final contract revision (from v1.1.0)

v1.2.0 applies the sixteen architecture decisions below, adds a durable commit ledger with crash recovery, separates reviewer authorization from agent authorization, and makes every file in the package consistent. The package is a contract only; it contains no application code. No statement in it claims that an implementation or tests have passed.

### Architecture decisions applied

| # | Decision | Where it is applied |
|---|---|---|
| 1 | Pure UUID v4 identifiers everywhere; the old `sess_`, `exec_`, `wh_`, `req_` prefixes are gone. `tool_execution_id` is now `operation_id` | All schemas, `tools.json`, every example, `API_CONTRACT.md` section 2 |
| 2 | Unknown tool: tool-level `BLOCK` (`400 INVALID_TOOL`, `POL-005`), but the session is **not** blocked solely for that | `policies.json` (`effect_scope`), `manifest.schema.json` (violation `effect_scope`), `API_CONTRACT.md` 5.2, 10.5 |
| 3 | Reviewer authorization is separate from agent authorization | New `AIRLOCK_REVIEWER_TOKEN`, `UNAUTHORIZED_REVIEWER`, `API_CONTRACT.md` section 3 |
| 4 | Session metadata and manifests live in a SQLite metadata DB, separate from speculative invoice DBs | `API_CONTRACT.md` 4.2, `.env.example` (`AIRLOCK_META_DB_PATH`) |
| 5 | Durable commit ledger in the production DB; receipt inserted in the same transaction as the mutations | `API_CONTRACT.md` 4.1, 8.1, 8.2; `api.schema.json` (`CommitLedgerReceipt`); `manifest.schema.json` (`ledger_id`, `recovered`) |
| 6 | Bulk-delete filters use AND semantics; any missing requested ID fails the whole call | `tools.json`, `API_CONTRACT.md` 10.5 |
| 7 | `INVOICE_NOT_FOUND` added (404) | `error.schema.json`, `API_CONTRACT.md` section 9 |
| 8 | After a session-level `BLOCK`, mutating tool calls are rejected; inspection and rollback allowed | `policies.json` (`session_block_lockout`), `API_CONTRACT.md` 5.5 |
| 9 | No automatic session expiry; documented as a limitation | `API_CONTRACT.md` section 13 |
| 10 | Secrets in webhook payloads are detected and blocked; secrets redacted from stored arguments, manifests, logs and responses | `policies.json` (`webhook_scan`, `redaction`), `API_CONTRACT.md` 3.7 |
| 11 | `POL-002` stays at 25%, with its own documented rationale | `policies.json` |
| 12 | Precedence `BLOCK > REQUIRE_APPROVAL > ALLOW` | `policies.json`, `API_CONTRACT.md` 5.1 and 5.4 |
| 13 | `ALLOW` never auto-commits | `API_CONTRACT.md` 5.1 |
| 14 | Webhooks are staged only, never dispatched | `tools.json`, `API_CONTRACT.md` 7.5 |
| 15 | Backend binds to `127.0.0.1` by default | `.env.example`, `API_CONTRACT.md` 3.4 |
| 16 | No agent can access the production database directly | `API_CONTRACT.md` section 1 and 3.4, `.env.example` trust boundaries |

### Corrected commit protocol (`API_CONTRACT.md` section 8)
- Requires the reviewer bearer token.
- `BEGIN IMMEDIATE` on production; a ledger guard; validate **all** mutations before applying any (version and full-row equality for updates and deletes, non-existence for inserts); collect all conflicts; apply all mutations; insert the ledger receipt **in the same transaction**; one `COMMIT`; any failure rolls everything back.
- Ledger table `airlock_commit_ledger` with `UNIQUE(session_id)` and enough data (counts, reviewer, reason, timestamp, SHA-256 `mutation_digest`) to identify and recover the commit.
- Crash recovery: startup reconciliation (and lazy reconciliation before commit and rollback) finalizes a `COMPLETED` session that has a receipt **without replaying mutations**. A rollback or second commit in that window returns `409 SESSION_ALREADY_FINALIZED`.
- The production database file is never replaced by a speculative database.

### Changes by file
- **`API_CONTRACT.md`**: rewritten around the decisions above. New sections: operation classes and endpoint summary, two bearer credentials, storage model (production + ledger, metadata, speculative), session lockout after `BLOCK`, commit recovery, known limitations. Demo scenario extended with a crash-recovery part; contract test table grown to 30 rows. Every JSON example is annotated with the schema it must validate against.
- **`manifest.schema.json`**: UUID v4 patterns; `agent_summary`; one shared `Mutation` definition (`mutation_id`, `operation_id`, `tool_name`, `entity_type`, `entity_id`, `mutation_type`, nullable `before`/`after`, `changed_fields`, `baseline_version`, `timestamp`, `policy_decision`); policy violations gain `stage`, nullable `operation_id`, `effect_scope`; history entries gain `tool_decision` and nullable `read_only`; staged webhooks gain `operation_id`; conflict details gain `entity_type`, `conflict_type` (`MISSING`, `MODIFIED`, `UNEXPECTED_EXISTING`) and nullable `expected_version`/`actual_version`; `finalization_result` gains `ledger_id` and `recovered`; lifecycle consistency rules (status vs timestamps vs review vs gate); machine-readable `x-state-machine`.
- **`api.schema.json`** (new): request and response schemas for all nine endpoints, typed error `details`, and `CommitLedgerReceipt`.
- **`error.schema.json`**: added `FORBIDDEN`, `INTERNAL_ERROR`, `INVOICE_NOT_FOUND` and (needed by decision 3) `UNAUTHORIZED_REVIEWER`; every code is bound to exactly one HTTP status by schema; `request_id` is UUID v4; examples included.
- **`tools.json`**: argument and result schemas for every tool; `bulk_delete_invoices` AND semantics, `INVOICE_NOT_FOUND` on a missing requested ID, `unmatched_invoice_ids`; `stage_webhook` records 0 mutations; examples use UUID v4 and a complete 420-ID list; error examples added; `update_invoice` rejects secret markers in `notes`.
- **`policies.json`**: `POL-001` threshold 10 → **80**; thresholds are integers compared with strict greater-than and integer arithmetic; `POL-002` kept at 25 with a rationale; every policy has `effect_scope` and `rationale`; `threshold_test_vectors` (400 no, 401 yes, 420 yes); `gate_rules`, `session_block_lockout`, `webhook_scan`, `redaction`.
- **`invoice.schema.json`**: unchanged field set (the canonical structure); added SQLite DDL, field roles, deterministic seed rules and fixed records.
- **`README.md`**: corrected the session-state checklist (commit on `ACTIVE` is `409 INVALID_SESSION_STATE`, not a concurrency conflict), compares logical content hashes instead of raw file bytes, documents local-only assumptions, new error codes and how to validate.
- **`.env.example`**: `AIRLOCK_HOST=127.0.0.1`, `AIRLOCK_DEMO_MODE=true`, `NEXT_PUBLIC_AIRLOCK_API_URL=http://127.0.0.1:8000`, reviewer token, metadata DB path, trust-boundary sections.
- **New**: `examples/*.json` (four complete example manifests), `scripts/validate_contracts.py`, this changelog.

### Behavior changes from v1.1.0
- Unknown tool no longer sets the session gate to `BLOCK` (v1.1.0 did).
- `commit`, `rollback` and `reset` now require a reviewer bearer token (v1.1.0: unauthenticated with an `Origin` check). The `Origin` check was dropped because header-based bearer tokens are not sent by cross-site requests; `FORBIDDEN` now covers only the reset guards.
- A missing invoice is `404 INVOICE_NOT_FOUND` (v1.1.0: `422 INVALID_ARGUMENTS`).
- Mutating tools are rejected after a session `BLOCK` (v1.1.0: still accepted).
- Thresholds are whole-number integers (`80`, `25`), not decimals (`80.0`).
- Violations carry `effect_scope`; the gate considers only `SESSION`-scope blocks.
- `update_invoice` rejects secret markers in `notes` (422), because mutation records are replayed verbatim at commit and must never be redacted.

### Decisions that still require human approval
1. **Reviewer credential delivery**: typed into the dashboard and held in memory (chosen) versus a Next.js server route holding it.
2. **`UNAUTHORIZED_REVIEWER`** was added beyond the three requested error codes, because separating reviewer from agent authorization needs a distinct code.
3. **`POL-002` at 25%** is an MVP placeholder pending business input.
4. **Unknown-tool risk display**: a tool-scope `BLOCK` leaves the gate `ALLOW` while `overall_risk_level` becomes `CRITICAL`; confirm that is the desired reviewer signal.
5. **Digest-mismatch recovery**: reconciliation finalizes from the ledger receipt even if the recomputed digest differs, logging CRITICAL; confirm.
6. **Rejecting secret markers in `update_invoice.notes`** (an addition driven by the no-redaction rule for invoice rows).
7. **Added files** beyond the requested set: `api.schema.json`, `examples/`, `scripts/validate_contracts.py`.

### Validation scope
`scripts/validate_contracts.py` uses its own validator for the JSON Schema keywords these files use. It is not a general JSON Schema implementation and should be complemented with a standard validator (see `contracts/README.md`). The cross-file text checks are keyword-based.
