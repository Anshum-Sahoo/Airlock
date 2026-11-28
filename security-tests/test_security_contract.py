"""Security contract tests against the real FastAPI app and disposable SQLite databases."""

from contextlib import ExitStack, closing
from importlib import import_module, reload
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
AGENT = "qa-synthetic-agent"
REVIEWER = "qa-synthetic-reviewer"
ORIGIN = "http://localhost:3000"
SESSIONS = "/api/sessions"
EXECUTE = "/api/tools/execute"
RESET = "/api/demo/reset"
DETAIL = SESSIONS + "/{session_id}"
COMPLETE = DETAIL + "/complete"
COMMIT = DETAIL + "/commit"
ROLLBACK = DETAIL + "/rollback"
REVIEW = {"reviewer": "qa@example.invalid"}


def contract(path):
    return json.loads((ROOT / "contracts" / path).read_text(encoding="utf-8"))


class PublishedExamples(unittest.TestCase):
    def test_dangerous_example_records_threshold_and_blocked_webhook(self):
        manifest = contract("examples/manifest.dangerous-completed.json")
        self.assertEqual(manifest["baseline_record_count"], 500)
        self.assertEqual(manifest["mutation_counts"]["deleted"], 420)
        self.assertEqual(manifest["gate_decision"], "BLOCK")
        self.assertEqual(
            {v["policy_id"]: v["decision"] for v in manifest["policy_violations"]},
            {"POL-001": "REQUIRE_APPROVAL", "POL-003": "BLOCK", "POL-004": "BLOCK"},
        )
        self.assertEqual(
            [(w["status"], w["payload"]) for w in manifest["staged_webhooks"]],
            [("BLOCKED", {"token": "[REDACTED]"})],
        )

    def test_recovered_example_identifies_same_receipt_and_mutations(self):
        committed = contract("examples/manifest.safe-committed.json")
        recovered = contract("examples/manifest.safe-recovered.json")
        self.assertEqual(committed["mutations"], recovered["mutations"])
        normal = committed["finalization_result"]
        self.assertIs(normal["recovered"], False)
        self.assertEqual(recovered["finalization_result"], dict(normal, recovered=True))


class LiveSecurity(unittest.TestCase):
    def setUp(self):
        try:
            from fastapi.testclient import TestClient
        except ModuleNotFoundError as error:
            self.skipTest(f"not implemented/not testable: runtime dependency {error.name}; install requirements.txt")
        from backend.app.config import get_settings

        stack = self.enterContext(ExitStack())
        self.directory = Path(stack.enter_context(TemporaryDirectory()))
        self.prod = self.directory / "prod.db"
        self.meta = self.directory / "meta.db"
        self.spec = self.directory / "speculative"
        stack.enter_context(patch.dict("os.environ", {
            "AIRLOCK_HOST": "127.0.0.1",
            "AIRLOCK_PORT": "8000",
            "AIRLOCK_DEMO_MODE": "true",
            "AIRLOCK_PROD_DB_PATH": str(self.prod),
            "AIRLOCK_META_DB_PATH": str(self.meta),
            "AIRLOCK_SPECULATIVE_DIR": str(self.spec),
            "AIRLOCK_CONTRACTS_DIR": str(ROOT / "contracts"),
            "AIRLOCK_AGENT_TOKEN": AGENT,
            "AIRLOCK_REVIEWER_TOKEN": REVIEWER,
            "CORS_ORIGINS": ORIGIN,
        }))
        get_settings.cache_clear()
        stack.callback(get_settings.cache_clear)
        app = reload(import_module("backend.app.main")).app
        self.routes = {(method.upper(), path) for path, operations in app.openapi()["paths"].items()
                       for method in operations}
        self.client = TestClient(app, base_url="http://127.0.0.1",
                                 client=("127.0.0.1", 50000),
                                 follow_redirects=False, raise_server_exceptions=False)
        self.stack = stack

    def start(self, *routes):
        required = {("POST", RESET), *routes}
        missing = sorted(required - self.routes)
        if missing:
            self.skipTest("not implemented/not testable: " +
                          ", ".join(f"{method} {path}" for method, path in missing))
        self.stack.enter_context(self.client)
        return self.expect(self.post(RESET, {}, REVIEWER, ORIGIN), 200)

    def post(self, path, body, token=AGENT, origin=None):
        headers = {"Authorization": f"Bearer {token}"}
        if origin is not None:
            headers["Origin"] = origin
        return self.client.post(path, json=body, headers=headers)

    def expect(self, response, status, code=None):
        self.assertEqual(response.status_code, status)
        body = response.json()
        if code:
            error = body["error"]
            self.assertEqual(error["code"], code)
            self.assertEqual(error["http_status"], status)
        return body

    def create(self):
        body = self.expect(self.post(SESSIONS, {"agent_name": "synthetic QA"}), 201)
        self.assertEqual(body["baseline_record_count"], 500)
        return body["session_id"]

    def tool(self, session_id, name, arguments):
        return self.post(EXECUTE, self.invocation(session_id, name, arguments))

    def invocation(self, session_id, name, arguments):
        return {"session_id": session_id, "tool_name": name, "arguments": arguments}

    def update(self, session_id, invoice_id, notes="Synthetic QA change"):
        self.expect(self.tool(session_id, "update_invoice", {
            "invoice_id": invoice_id, "notes": notes,
        }), 200)

    def complete(self, session_id):
        return self.expect(self.post(COMPLETE.format(session_id=session_id), {}), 200)

    def manifest(self, session_id):
        return self.expect(self.client.get(DETAIL.format(session_id=session_id)), 200)

    def finalize(self, route, session_id):
        return self.post(route.format(session_id=session_id), REVIEW, REVIEWER, ORIGIN)

    def production(self):
        # Both tables must be read from the same SQLite snapshot.
        with closing(sqlite3.connect(self.prod.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            invoices = {row["id"]: dict(row) for row in db.execute("SELECT * FROM invoices")}
            receipts = [dict(row) for row in db.execute(
                "SELECT * FROM airlock_commit_ledger ORDER BY session_id")]
        return invoices, receipts

    def test_seed_distribution(self):
        response = self.start()
        invoices, receipts = self.production()
        self.assertEqual(response["prod_invoice_count"], 500)
        self.assertEqual(response["overdue_count"], 420)
        self.assertEqual(response["non_overdue_count"], 80)
        self.assertEqual(len(invoices), 500)
        self.assertEqual(sum(row["status"] == "OVERDUE" for row in invoices.values()), 420)
        self.assertEqual({row["version"] for row in invoices.values()}, {1})
        self.assertEqual(receipts, [])

    def threshold(self, count, gate):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE))
        before = self.production()
        session_id = self.create()
        arguments = {"invoice_ids": [f"INV-{i:04}" for i in range(1, count + 1)]}
        result = self.expect(self.tool(session_id, "bulk_delete_invoices", arguments), 200)
        self.assertEqual(result["mutations_recorded"], count)
        manifest = self.complete(session_id)
        self.assertEqual(manifest["gate_decision"], gate)
        self.assertEqual(manifest["human_review_status"], "PENDING")
        self.assertEqual(manifest["mutation_counts"]["deleted"], count)
        violations = [v for v in manifest["policy_violations"] if v["policy_id"] == "POL-001"]
        self.assertEqual(len(violations), int(gate == "REQUIRE_APPROVAL"))
        for violation in violations:
            self.assertEqual(violation["decision"], "REQUIRE_APPROVAL")
            self.assertEqual(violation["effect_scope"], "SESSION")
            self.assertEqual(violation["affected_record_count"], count)
        self.assertEqual(self.production(), before)

    def test_delete_400(self):
        self.threshold(400, "ALLOW")

    def test_delete_401(self):
        self.threshold(401, "REQUIRE_APPROVAL")

    def test_delete_420(self):
        self.threshold(420, "REQUIRE_APPROVAL")

    def test_unknown_tool_is_tool_scoped(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE))
        session_id = self.create()
        prior = self.expect(self.tool(session_id, "get_invoice", {"invoice_id": "INV-0001"}), 200)
        error = self.expect(self.tool(session_id, "qa_unknown_tool", {}), 400, "INVALID_TOOL")
        details = error["error"]["details"]
        self.assertEqual(details["session_gate_decision"], "PENDING")
        self.assertEqual([(v["policy_id"], v["effect_scope"]) for v in details["policy_violations"]],
                         [("POL-005", "TOOL")])
        after = self.expect(self.tool(session_id, "get_invoice", {"invoice_id": "INV-0001"}), 200)
        self.assertEqual(after["result"], prior["result"])
        manifest = self.complete(session_id)
        self.assertEqual(manifest["gate_decision"], "ALLOW")
        self.assertEqual(manifest["mutation_counts"]["total"], 0)
        history = [row for row in manifest["tool_execution_history"]
                   if row["operation_id"] == details["operation_id"]]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "BLOCKED")
        self.assertEqual(history[0]["mutations_recorded"], 0)

    def check_reviewer_guards(self, origin_cases):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE),
                   ("POST", COMMIT), ("POST", ROLLBACK), ("GET", DETAIL))
        session_id = self.create()
        self.update(session_id, "INV-0001")
        self.complete(session_id)
        before = self.production()
        manifest = self.manifest(session_id)
        for route in (COMMIT, ROLLBACK, RESET):
            body = {} if route == RESET else REVIEW
            for token, origin, status, code in origin_cases:
                with self.subTest(route=route, origin=origin, status=status):
                    response = self.post(route.format(session_id=session_id), body, token, origin)
                    self.expect(response, status, code)
                    self.assertEqual(self.production(), before)
                    self.assertEqual(self.manifest(session_id), manifest)
                    self.assertTrue((self.spec / f"{session_id}.db").is_file())

    def test_agent_token_rejected_for_reviewer_actions(self):
        self.check_reviewer_guards([(AGENT, ORIGIN, 401, "UNAUTHORIZED_REVIEWER")])

    def test_missing_and_unlisted_origin_rejected_before_credentials(self):
        self.check_reviewer_guards([
            (token, origin, 403, "FORBIDDEN")
            for origin in (None, "http://unlisted.example.invalid")
            for token in (REVIEWER, AGENT)
        ])

    def test_reviewer_token_rejected_for_agent_actions(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE), ("GET", DETAIL))
        session_id = self.create()
        manifest = self.manifest(session_id)
        before = self.production()
        spec_files = sorted(self.spec.iterdir())
        for path, body in (
            (SESSIONS, {"agent_name": "second synthetic QA"}),
            (EXECUTE, self.invocation(session_id, "update_invoice", {
                "invoice_id": "INV-0001", "notes": "should never apply",
            })),
            (COMPLETE.format(session_id=session_id), {}),
        ):
            with self.subTest(path=path):
                self.expect(self.post(path, body, REVIEWER), 401, "UNAUTHORIZED_AGENT")
        self.assertEqual(self.manifest(session_id), manifest)
        self.assertEqual(self.production(), before)
        self.assertEqual(sorted(self.spec.iterdir()), spec_files)

    def webhook(self, host, payload, policy_id, marker=None):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE),
                   ("POST", ROLLBACK), ("POST", COMMIT))
        session_id = self.create()
        before = self.production()
        # Observe and block DNS/TCP while the real app handles the webhook lifecycle.
        with patch("socket.getaddrinfo", side_effect=AssertionError("unexpected DNS")) as dns, \
             patch("socket.socket.connect", side_effect=AssertionError("unexpected connect")) as tcp, \
             patch("socket.socket.connect_ex", side_effect=AssertionError("unexpected connect_ex")) as tcp_ex:
            response = self.tool(session_id, "stage_webhook", {
                "url": f"https://{host}/qa", "event_type": "invoice.updated", "payload": payload,
            })
            error = self.expect(response, 403, "POLICY_BLOCK")
            manifest = self.complete(session_id)
            self.expect(self.finalize(COMMIT, session_id), 403, "POLICY_BLOCK")
            rejected = self.expect(self.finalize(ROLLBACK, session_id), 200)
            dns.assert_not_called()
            tcp.assert_not_called()
            tcp_ex.assert_not_called()
        self.assertEqual(manifest["gate_decision"], "BLOCK")
        self.assertEqual([v["policy_id"] for v in manifest["policy_violations"]], [policy_id])
        entries = manifest["staged_webhooks"]
        self.assertEqual([w["status"] for w in entries], ["BLOCKED"])
        self.assertEqual(rejected["staged_webhooks"], entries)
        self.assertEqual(self.production(), before)
        if marker:
            self.assertEqual(entries[0]["payload"], {"token": "[REDACTED]"})
            self.assertNotIn(marker, json.dumps([error, manifest, rejected]))

    def test_secret_webhook_is_blocked_and_redacted(self):
        marker = "AIRLOCK_SECRET_TEST_SYNTHETIC_QA"
        self.webhook("hooks.airlock.internal", {"token": marker}, "POL-003", marker)

    def test_unlisted_webhook_is_blocked(self):
        self.webhook("unlisted.example.invalid", {"invoice_id": "INV-0001"}, "POL-004")

    def test_rejection_preserves_all_production_rows_and_receipts(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE), ("POST", ROLLBACK))
        before = self.production()
        session_id = self.create()
        self.update(session_id, "INV-0001")
        completed = self.complete(session_id)
        rejected = self.expect(self.finalize(ROLLBACK, session_id), 200)
        self.assertEqual(rejected["execution_status"], "ROLLED_BACK")
        self.assertEqual(rejected["human_review_status"], "REJECTED")
        self.assertEqual(rejected["mutations"], completed["mutations"])
        self.assertFalse((self.spec / f"{session_id}.db").exists())
        self.assertEqual(self.production(), before)

    def stage_two_updates(self):
        session_id = self.create()
        self.update(session_id, "INV-0001")
        self.update(session_id, "INV-0002")
        return session_id, self.complete(session_id)

    def expect_commit_snapshot(self, session_id, completed, before, ledger_id):
        invoices, receipts = before
        expected = dict(invoices)
        for mutation in completed["mutations"]["updated"]:
            expected[mutation["entity_id"]] = mutation["after"]
        actual, ledger = self.production()
        self.assertEqual(actual, expected)
        self.assertEqual(len(ledger), len(receipts) + 1)
        receipt = next(row for row in ledger if row["session_id"] == session_id)
        self.assertEqual(receipt["ledger_id"], ledger_id)

    def test_safe_commit_and_duplicate_finalization(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE),
                   ("POST", COMMIT), ("POST", ROLLBACK))
        before = self.production()
        session_id, completed = self.stage_two_updates()
        self.assertEqual(self.production(), before)
        committed = self.expect(self.finalize(COMMIT, session_id), 200)
        result = committed["finalization_result"]
        self.assertEqual(committed["execution_status"], "COMMITTED")
        self.assertEqual(committed["human_review_status"], "APPROVED")
        self.assertEqual(result["applied_counts"], {"inserted": 0, "updated": 2, "deleted": 0})
        self.assertIs(result["recovered"], False)
        self.expect_commit_snapshot(session_id, completed, before, result["ledger_id"])
        after = self.production()
        for route in (COMMIT, ROLLBACK):
            self.expect(self.finalize(route, session_id), 409, "SESSION_ALREADY_FINALIZED")
            self.assertEqual(self.production(), after)

    def test_commit_conflict_does_not_apply_nonconflicting_row(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE),
                   ("POST", COMMIT), ("GET", DETAIL))
        session_id, _ = self.stage_two_updates()
        competing = self.create()
        self.update(competing, "INV-0002", "Competing synthetic update")
        self.complete(competing)
        self.expect(self.finalize(COMMIT, competing), 200)
        before = self.production()
        error = self.expect(self.finalize(COMMIT, session_id), 409, "COMMIT_CONFLICT")
        self.assertEqual([c["entity_id"] for c in error["error"]["details"]["conflicts"]],
                         ["INV-0002"])
        manifest = self.manifest(session_id)
        self.assertEqual(manifest["execution_status"], "COMPLETED")
        self.assertEqual(manifest["human_review_status"], "PENDING")
        self.assertEqual(manifest["finalization_result"]["status"], "FAILED")
        self.assertEqual(manifest["finalization_result"]["applied_counts"],
                         {"inserted": 0, "updated": 0, "deleted": 0})
        self.assertEqual(self.production(), before)

    def sql_fault(self, database, sql):
        # Test-only DDL against a TemporaryDirectory database.
        with closing(sqlite3.connect(database)) as db:
            db.executescript(sql)

    def test_failed_receipt_insert_rolls_back_invoice_writes(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE), ("POST", COMMIT))
        session_id, _ = self.stage_two_updates()
        before = self.production()
        self.sql_fault(self.prod, """
            CREATE TRIGGER qa_fail_receipt BEFORE INSERT ON airlock_commit_ledger
            BEGIN SELECT RAISE(ABORT, 'synthetic ledger failure'); END;
        """)
        self.expect(self.finalize(COMMIT, session_id), 500, "DATABASE_FAILURE")
        self.assertEqual(self.production(), before)

    def test_durable_commit_reconciles_on_retry_without_replay(self):
        self.start(("POST", SESSIONS), ("POST", EXECUTE), ("POST", COMPLETE),
                   ("POST", COMMIT), ("GET", DETAIL))
        session_id, completed = self.stage_two_updates()
        before = self.production()
        self.sql_fault(self.meta, """
            CREATE TRIGGER qa_fail_update BEFORE UPDATE ON sessions
            BEGIN SELECT RAISE(ABORT, 'synthetic metadata failure'); END;
            CREATE TRIGGER qa_fail_insert BEFORE INSERT ON sessions
            BEGIN SELECT RAISE(ABORT, 'synthetic metadata failure'); END;
        """)
        error = self.expect(self.finalize(COMMIT, session_id), 500, "DATABASE_FAILURE")
        details = error["error"]["details"]
        self.assertIs(details["commit_durable"], True)
        self.expect_commit_snapshot(session_id, completed, before, details["ledger_id"])
        after = self.production()
        self.sql_fault(self.meta, "DROP TRIGGER qa_fail_update; DROP TRIGGER qa_fail_insert;")
        self.expect(self.finalize(COMMIT, session_id), 409, "SESSION_ALREADY_FINALIZED")
        result = self.manifest(session_id)["finalization_result"]
        self.assertIs(result["recovered"], True)
        self.assertEqual(result["ledger_id"], details["ledger_id"])
        self.assertEqual(self.production(), after)
