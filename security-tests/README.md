# Airlock security regression tests

From the repository root, use the Python 3.12 environment described in TEAM_WORKFLOW.md and install requirements.txt.

```powershell
python scripts/validate_contracts.py
python -m unittest discover -s security-tests -v
```

The two published-example tests check frozen contract fixtures. They provide no evidence about backend behavior. The live tests use the real FastAPI application in process, with distinct synthetic credentials and fresh temporary production, metadata, and speculative databases for each test. No external Airlock instance or real credentials are needed. The suite reads production via read-only SQLite snapshots. The two fault-injection tests install abort triggers only in the disposable databases.

A missing runtime dependency or a required route missing from OpenAPI produces a **not implemented/not testable** skip. Once all required routes are registered, unexpected responses, including redirects, 404s, and 501s, fail the tests. The live tests use `POST /api/demo/reset` as the entry point for loading the seed so they exercise the actual seeder. If the seeder ships separately, seed coverage through reset remains pending.

| Live coverage | Required backend behavior |
| --- | --- |
| 500 rows, 420 overdue and 80 non-overdue, and version 1 | `POST /api/demo/reset` and the synthetic seeder |
| 400, 401, and 420 deletion boundaries, with no implicit production writes | `POST /api/sessions`, `POST /api/tools/execute`, and `POST /api/sessions/{session_id}/complete` |
| Unknown tool blocked and audited at tool scope, read-only inspection still works, session can complete with ALLOW | Session creation, execution, and completion |
| Credential separation and missing or unlisted Origin, including error precedence and state preservation | Session creation and detail, tool execution, completion, commit, rollback, and reset |
| Secret marker and unlisted webhook blocked, synthetic token redacted in returned data, no in-process DNS/TCP dispatch observed | Tool execution, completion, commit denial, and rollback |
| Reviewer rejection preserves production rows and receipts | Completion and `POST /api/sessions/{session_id}/rollback` |
| Safe commit updates two invoices and writes one receipt; receipt-insert failure rolls back writes | `POST /api/sessions/{session_id}/commit`, ledger insertion, and the SQLite transaction |
| Conflicts leave the nonconflicting row and ledger unchanged; duplicate finalization and retry recovery do not replay | Commit, rollback, session detail, and durable-ledger reconciliation |

The starter documents all live scenarios above as **not implemented/not testable**. The current workflow runs the starter suite under `backend/tests/`. Run the security suite with the explicit discovery command until CI placement is agreed with the integration lead.

## Follow-up with the integration lead

- Which integration fixture should cover the seeder if it lands before the reset route?
- Is there a supported crash hook for restart reconciliation? The suite exercises the required commit-retry recovery path with a temporary SQLite fault. Startup recovery, process interruption before SQLite commit, and simultaneous finalization are still uncovered.
- Which log capture and egress observation should be used once the backend logging and transport are available? The suite inspects the response and manifests for redaction and observes in-process Python DNS/TCP calls. Persisted metadata/log redaction and subprocess egress are still uncovered.
