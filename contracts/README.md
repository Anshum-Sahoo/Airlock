# Airlock Contracts Package (v1.2.1)

This directory is the single source of truth for **Airlock — The Security Gateway for Autonomous AI Agents**. All four team members implement against these contracts during the 36-hour hackathon sprint. The package is a contract only; it contains no application code.

## File Inventory

| File | Format | Purpose | Primary Owner | Consumers |
|---|---|---|---|---|
| `API_CONTRACT.md` | Markdown | REST API specification, security model, policy precedence, state machine, commit/recovery protocol, demo scenario, contract test table | Member 1 & Member 4 | All Members |
| `manifest.schema.json` | JSON Schema (2020-12) | Session manifest: net mutation records, violations, tool history, finalization result, conflict details, state machine | Member 1 | Member 2, Member 4 |
| `api.schema.json` | JSON Schema (2020-12) | Request/response schemas for every endpoint, typed error `details`, commit-ledger receipt (new in v1.2.0) | Member 1 | Member 2, Member 3, Member 4 |
| `tools.json` | JSON | Allowlisted agent tool definitions, argument and result schemas, examples | Member 1 & Member 3 | Member 1, Member 3, Member 4 |
| `policies.json` | JSON | Deterministic rules, integer thresholds, allowlists, redaction, precedence (`BLOCK > REQUIRE_APPROVAL > ALLOW`) | Member 1 | Member 1, Member 2, Member 4 |
| `invoice.schema.json` | JSON Schema (2020-12) | Canonical invoice record, SQLite DDL, seed rules (`INV-0001` to `INV-0500`) | Member 1 & Member 4 | Member 1, Member 3, Member 4 |
| `error.schema.json` | JSON Schema (2020-12) | Error envelope and the error-code to HTTP-status mapping | Member 1 | All Members |
| `examples/*.json` | JSON | Complete example manifests (safe commit, recovered commit, 420-deletion demo, unknown-tool attempt) | Member 4 | Member 1, Member 2 |
| `README.md` | Markdown | This overview | Member 4 | All Members |
| `../scripts/validate_contracts.py` | Python 3 | Standard-library contract validator | Member 4 | All Members |
| `../.env.example` | Env | Environment variables grouped by trust boundary | Member 1 & Member 3 | All Members |
| `../CHANGELOG.md` | Markdown | Changes from v1.1.0 and v1.2.0 | Member 4 | All Members |

## Endpoints at a Glance

| Method | Path | Class | Authentication |
|---|---|---|---|
| `GET` | `/api/health` | local-read | none |
| `POST` | `/api/sessions` | agent-only | agent bearer token |
| `GET` | `/api/sessions` | local-read | none |
| `GET` | `/api/sessions/{session_id}` | local-read | none |
| `POST` | `/api/tools/execute` | agent-only | agent bearer token |
| `POST` | `/api/sessions/{session_id}/complete` | agent-only | agent bearer token |
| `POST` | `/api/sessions/{session_id}/commit` | reviewer-only | reviewer bearer token + Origin allowlist |
| `POST` | `/api/sessions/{session_id}/rollback` | reviewer-only | reviewer bearer token + Origin allowlist |
| `POST` | `/api/demo/reset` | local-demo-only | reviewer bearer token + Origin allowlist + demo guards |

## Local-Only Security Assumptions

- The backend binds to `127.0.0.1` and is meant to run on the demo machine only. The three read endpoints have **no authentication** under this explicit local-only assumption.
- Agent and reviewer authorization are **separate**: `AIRLOCK_AGENT_TOKEN` (agent-only endpoints) and `AIRLOCK_REVIEWER_TOKEN` (commit, rollback, reset). The agent token never authorizes reviewer actions. Startup fails if either is empty or if they are equal.
- The reviewer token is typed by the human reviewer into the dashboard and kept in page memory. It is never a `NEXT_PUBLIC_*` variable and never bundled. `NVIDIA_API_KEY` and both tokens must never reach the browser or any API response.
- CORS is **not** authentication (`CORSMiddleware` only governs browser response visibility). In addition to `TrustedHostMiddleware` (`localhost`, `127.0.0.1`, `[::1]`) and `Authorization: Bearer <AIRLOCK_REVIEWER_TOKEN>`, the backend enforces an exact server-side `Origin` allowlist check against `CORS_ORIGINS` **before** authentication or any state change on `POST /api/sessions/{session_id}/commit`, `POST /api/sessions/{session_id}/rollback`, and `POST /api/demo/reset`, returning `403 FORBIDDEN` when `Origin` is missing or unlisted. `X-Forwarded-For` and arbitrary `Host` headers are never trusted.
- Non-browser local testing clients (`curl`, `pytest`/`httpx`) MUST explicitly supply an allowlisted `Origin` header (e.g. `Origin: http://localhost:3000`) alongside `AIRLOCK_REVIEWER_TOKEN` when calling `commit`, `rollback`, or `reset`.
- `POST /api/demo/reset` additionally requires `AIRLOCK_DEMO_MODE=true` and a loopback client.
- The agent process gets no database path and no access to the production or metadata databases.
- Secrets (`secret_markers` in `policies.json`) found in webhook payloads are blocked; they are redacted from every stored argument, manifest, log line and response.
- Known MVP limits: no automatic session expiry, marker-based secret detection only, one shared token per role. See `API_CONTRACT.md` section 13.

## Responsibility Matrix

| Contract / Artifact | Member 1 (Backend & Security) | Member 2 (Frontend) | Member 3 (AI Agent) | Member 4 (Testing & Integration) |
|---|---|---|---|---|
| `API_CONTRACT.md` | **Owns / Implements** | Consumes | Consumes | Validates |
| `manifest.schema.json`, `api.schema.json` | **Produces / Persists** | Consumes (Dashboard & Diff UI) | — | Validates (schema tests) |
| `tools.json` | **Enforces** | — | **Consumes** (Nemotron tool definitions) | Validates (tool tests) |
| `policies.json` | **Enforces** | Displays violations | — | Validates (security tests) |
| `invoice.schema.json` | **Stores / Diffs** | Displays diffs | Reads/mutates via tools | **Generates the 500 seeded rows** |
| `error.schema.json` | **Emits** | Renders error states | Handles retries/blocks | Validates error codes |
| `.env.example` | **Owns backend vars** | Owns `NEXT_PUBLIC_*` vars | **Owns `NVIDIA_*` and agent vars** | Verifies setup |

## Contract Validation Checklist

Before integration testing begins, Member 4 should verify:

1. **JSON validity**: every `.json` file parses with zero syntax errors.
2. **Schema compliance**:
   - `POST …/complete`, `POST …/commit`, `POST …/rollback` and `GET /api/sessions/{session_id}` responses validate against `manifest.schema.json`.
   - Other success bodies validate against `api.schema.json` (`$defs/HealthResponse`, `CreateSessionResponse`, `SessionListResponse`, `ExecuteSuccessResponse`, `ResetResponse`).
   - Every error response (`400`, `401`, `403`, `404`, `409`, `422`, `500`) validates against `error.schema.json`, and its `details` against the matching `api.schema.json` `$defs/*Details`.
   - Every seeded invoice validates against `invoice.schema.json` (420 `OVERDUE`: `INV-0001`..`INV-0420`; 80 non-overdue), contains no secret marker, and starts at `version` 1.
3. **Identifiers**: every identifier except invoice IDs is a UUID v4.
4. **Tool allowlist parity**: Member 3's Nemotron tool definitions match `tools.json` names, required fields and types exactly. An unknown tool returns `400 INVALID_TOOL` with a tool-level `BLOCK` (`POL-005`) and **does not** block the whole session.
5. **Policy precedence**: `BLOCK` overrides `REQUIRE_APPROVAL`, which overrides `ALLOW`; an `ALLOW` never auto-commits. After a session-level `BLOCK`, mutating tools return `403 POLICY_BLOCK` (`SESSION_BLOCKED`), read-only tools, `/complete` and `/rollback` still work, and `/commit` returns `403 POLICY_BLOCK`.
6. **Thresholds** (baseline 500): deleting exactly 400 does **not** trigger `POL-001`; 401 and 420 do (strictly greater than 80%, integer arithmetic). `POL-002` stays at 25% (125 no, 126 yes).
7. **Session states**: `ACTIVE` → `COMPLETED` → `COMMITTED` or `ROLLED_BACK`; `/commit` on an `ACTIVE` session returns `409 INVALID_SESSION_STATE`; `execute` after `/complete` returns `409 INVALID_SESSION_STATE`; any lifecycle call on a `COMMITTED` or `ROLLED_BACK` session returns `409 SESSION_ALREADY_FINALIZED`. A failed commit leaves the session `COMPLETED` with review status `PENDING`.
8. **Isolation & rollback proof**: rejecting a session via `POST /api/sessions/{session_id}/rollback` deletes its speculative `.db` file and leaves `airlock_prod.db` **logically identical**. Compare a **logical content hash**, not raw file bytes (SQLite WAL and page layout can change file bytes without changing data): read `SELECT * FROM invoices ORDER BY id`, serialize each row with the columns of `invoice.schema.json` in `x-sqlite.column_order`, and take a SHA-256 of the canonical JSON.
9. **Concurrency conflict proof**: modifying, deleting or silently editing an invoice in `airlock_prod.db` after the session was created makes `POST …/commit` abort with `409 COMMIT_CONFLICT`, with no partial changes, no ledger row, and the session still `COMPLETED`.
10. **Commit ledger & recovery**: a successful commit inserts exactly one `airlock_commit_ledger` receipt (unique per `session_id`) in the **same SQLite transaction** as the mutations. After a crash between the production commit and the metadata update, startup reconciliation finds the receipt and finalizes the session (`recovered: true`) **without replaying** mutations; a retried commit or a rollback in that window returns `409 SESSION_ALREADY_FINALIZED`.
11. **Webhook safety**: `stage_webhook` never performs outbound HTTP; webhooks appear only in `manifest.staged_webhooks` and stay `STAGED` or `BLOCKED`.
12. **Secret boundary**: no secret marker, `NVIDIA_API_KEY`, `AIRLOCK_AGENT_TOKEN` or `AIRLOCK_REVIEWER_TOKEN` appears in any API response, the metadata database, logs or Next.js client bundles.
13. **Server-side `Origin` allowlist**: `commit`, `rollback`, and `reset` reject missing or non-`CORS_ORIGINS` `Origin` headers with `403 FORBIDDEN` before auth or mutation; non-browser tests pass `Origin: http://localhost:3000`.

## Error Codes

`error.schema.json` maps each code to exactly one HTTP status. Added in v1.2.0 / v1.2.1: `INVOICE_NOT_FOUND` (404), `UNAUTHORIZED_REVIEWER` (401), `FORBIDDEN` (403 — demo reset guards and disallowed/missing `Origin` on `commit`/`rollback`/`reset`), `INTERNAL_ERROR` (500). Existing: `INVALID_SESSION` (404), `INVALID_TOOL` (400), `INVALID_ARGUMENTS` (422), `UNAUTHORIZED_AGENT` (401), `INVALID_SESSION_STATE` (409), `POLICY_BLOCK` (403), `COMMIT_CONFLICT` (409), `DATABASE_FAILURE` (500), `SESSION_ALREADY_FINALIZED` (409).

## How to Validate the Contracts

From the package root (the directory that contains `contracts/` and `scripts/`):

```
python3 scripts/validate_contracts.py
```

It needs only the Python standard library (3.9 or newer). It parses every JSON file, lints the schemas, validates every example (fixtures, `tools.json` examples, error examples, and each annotated JSON block in `API_CONTRACT.md`) with a built-in validator, runs negative self-tests, and checks cross-file consistency (UUID v4, tools, policies, endpoints, status codes, state machine, invoice fields, thresholds, commit ledger, `.env.example`). The exit code is non-zero if any check fails.

The built-in validator implements only the JSON Schema keywords these files use; it is not a general implementation. For an independent second opinion, replay the same pairs with a standard validator: `python3 scripts/validate_contracts.py --dump-instances instances.json` writes every `(schema, instance)` pair. Load all four `*.schema.json` files into the validator's registry by their `$id` so cross-file `$ref`s resolve (for example with Python `jsonschema` 4.18+ and a `referencing` registry, or Ajv with `addSchema`). Every JSON block in `API_CONTRACT.md` carries an HTML comment naming its schema; blocks that are excerpts name the file they are a subset of.

## Integration Quickstart

1. Copy `.env.example` to `.env` (backend) and give the agent runner and the dashboard only the variables in their own sections.
2. Generate two different random tokens for `AIRLOCK_AGENT_TOKEN` and `AIRLOCK_REVIEWER_TOKEN`.
3. Seed 500 invoices following `invoice.schema.json → x-seed`; create the `airlock_commit_ledger` table beside `invoices`.
4. Start the backend on `127.0.0.1:8000` with a single worker, then the dashboard, then the agent.
5. Run `python3 scripts/validate_contracts.py` after every contract edit.
