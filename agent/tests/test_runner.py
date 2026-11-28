import copy
import json
import unittest
from unittest.mock import patch

import httpx

from agent.__main__ import delete_demo, nemotron_lookup, webhook_demo
from agent.client import CONTRACTS, TOOLS, AgentError, Airlock, ApiError

DELETE_ID = "3f2b8a1e-5c4d-4e7a-9b1f-0a6d2c8e4f10"
WEBHOOK_ID = "b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21"
TOKEN = "mock-agent-token"
TIMESTAMP = "2026-11-24T12:00:00Z"


def created(session_id, task):
    return {
        "session_id": session_id, "agent_name": "airlock-python-agent",
        "task_description": task, "execution_status": "ACTIVE", "gate_decision": "PENDING",
        "human_review_status": "PENDING", "baseline_record_count": 500, "created_at": TIMESTAMP,
    }


def manifest_fixture():
    return json.loads((CONTRACTS / "examples/manifest.dangerous-completed.json").read_bytes())


class RunnerTests(unittest.TestCase):
    def api(self, responses):
        self.requests = []
        remaining = iter(responses)

        def handle(request):
            self.assertEqual(request.url.host, "127.0.0.1")
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["authorization"], f"Bearer {TOKEN}")
            self.assertEqual(request.headers["content-type"], "application/json")
            self.requests.append((request.url.path, json.loads(request.content)))
            response = next(remaining)
            if response is None:
                raise httpx.ReadTimeout("ambiguous outcome", request=request)
            return response

        client = httpx.Client(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handle))
        self.addCleanup(client.close)
        return Airlock(client, TOKEN)

    def test_independent_demo_sessions(self):
        deletion = manifest_fixture()
        deletion["gate_decision"] = "REQUIRE_APPROVAL"
        deletion["policy_violations"] = [deletion["policy_violations"][-1]]
        deletion["tool_execution_history"] = deletion["tool_execution_history"][:1]
        deletion["staged_webhooks"] = []
        deletion["risk_summary"].update(
            overall_risk_level="HIGH", block_count=0, violation_count=1,
            summary_text="420 overdue invoices deleted (84% of baseline).",
        )
        webhook = manifest_fixture()
        webhook["session_id"] = WEBHOOK_ID
        webhook["mutation_counts"] = dict.fromkeys(webhook["mutation_counts"], 0)
        webhook["mutations"] = {key: [] for key in webhook["mutations"]}
        webhook["tool_execution_history"] = webhook["tool_execution_history"][1:]
        blocked = copy.deepcopy(TOOLS["stage_webhook"]["example_error_responses"][0]["response"])
        blocked["error"]["details"]["policy_violations"] = blocked["error"]["details"]["policy_violations"][:1]
        webhook["policy_violations"] = blocked["error"]["details"]["policy_violations"]
        webhook["staged_webhooks"][0]["url"] = "https://hooks.airlock.internal/collect"
        webhook["risk_summary"].update(
            affected_percentage=0, total_mutations=0, block_count=1, violation_count=1,
            require_approval_count=0, summary_text="Webhook blocked by the secret policy.",
        )
        api = self.api([
            httpx.Response(201, json=created(DELETE_ID, "Stage deletion of overdue demo invoices")),
            httpx.Response(200, json=TOOLS["bulk_delete_invoices"]["example_success_response"]),
            httpx.Response(200, json=deletion),
            httpx.Response(201, json=created(WEBHOOK_ID, "Demonstrate webhook secret policy")),
            httpx.Response(403, json=blocked),
            httpx.Response(200, json=webhook),
        ])
        deleted = delete_demo(api)
        self.assertEqual(deleted["gate_decision"], "REQUIRE_APPROVAL")
        self.assertEqual(deleted["mutation_counts"]["deleted"], 420)
        self.assertEqual(deleted["risk_summary"]["affected_percentage"], 84.0)
        denied = webhook_demo(api)
        self.assertEqual(denied["gate_decision"], "BLOCK")
        self.assertEqual(denied["tool_error"], "POLICY_BLOCK")
        self.assertEqual(denied["policy_ids"], ["POL-003"])
        self.assertEqual(denied["mutation_counts"]["total"], 0)
        self.assertNotIn("sk_live_", json.dumps(denied))
        self.assertEqual(self.requests, [
            ("/api/sessions", {"agent_name": "airlock-python-agent",
                               "task_description": "Stage deletion of overdue demo invoices"}),
            ("/api/tools/execute", {"session_id": DELETE_ID, "tool_name": "bulk_delete_invoices",
                                    "arguments": {"status": "OVERDUE"}}),
            (f"/api/sessions/{DELETE_ID}/complete", {"agent_summary": "Staged deletion of overdue invoices."}),
            ("/api/sessions", {"agent_name": "airlock-python-agent",
                               "task_description": "Demonstrate webhook secret policy"}),
            ("/api/tools/execute", {"session_id": WEBHOOK_ID, "tool_name": "stage_webhook", "arguments": {
                "url": "https://hooks.airlock.internal/collect", "event_type": "demo.secret_check",
                "payload": {"token": "sk_live_DEMO_REDACTED"},
            }}),
            (f"/api/sessions/{WEBHOOK_ID}/complete",
             {"agent_summary": "The webhook secret policy blocked the request."}),
        ])

    def test_transport_failure_does_not_retry_or_complete(self):
        api = self.api([httpx.Response(201, json=created(DELETE_ID, "demo")), None])
        with self.assertRaisesRegex(AgentError, "Outcome may be unknown"):
            delete_demo(api)
        self.assertEqual(len(self.requests), 2)

    def test_api_error_does_not_retry_or_complete(self):
        api = self.api([
            httpx.Response(201, json=created(DELETE_ID, "demo")),
            httpx.Response(500, json={"error": {
                "code": "DATABASE_FAILURE", "message": "Internal database error.",
                "http_status": 500, "timestamp": TIMESTAMP, "request_id": WEBHOOK_ID,
            }}),
        ])
        with self.assertRaisesRegex(ApiError, "500 DATABASE_FAILURE"):
            delete_demo(api)
        self.assertEqual(len(self.requests), 2)

    def test_rejects_unknown_tool_and_invalid_arguments_locally(self):
        api = self.api([])
        with self.assertRaisesRegex(AgentError, "allowlist"):
            api.execute(DELETE_ID, "run_sql", {})
        with self.assertRaisesRegex(AgentError, "Tool arguments"):
            api.execute(DELETE_ID, "bulk_delete_invoices", {"status": "OVERDUE", "extra": True})
        self.assertEqual(self.requests, [])

    def test_malformed_response_is_a_controlled_error(self):
        api = self.api([httpx.Response(403, text="Invalid host header")])
        with self.assertRaisesRegex(AgentError, "invalid JSON response"):
            api.create("tester", None)
        self.assertEqual(len(self.requests), 1)

    def test_nemotron_cannot_select_a_mutating_tool(self):
        api = self.api([])

        def model_handler(request):
            self.assertEqual(str(request.url), "https://models.example/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer mock-model-key")
            body = json.loads(request.content)
            self.assertEqual(body["model"], "mock-nemotron")
            self.assertEqual(
                {tool["function"]["name"] for tool in body["tools"]},
                {"get_invoice", "list_invoices"},
            )
            self.assertNotIn(TOKEN, request.content.decode())
            return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{
                "type": "function",
                "function": {"name": "bulk_delete_invoices", "arguments": "{}"},
            }]}}]})

        model_client = httpx.Client(
            base_url="https://models.example/v1", transport=httpx.MockTransport(model_handler),
        )
        env = {
            "NVIDIA_API_KEY": "mock-model-key",
            "NVIDIA_BASE_URL": "https://models.example/v1",
            "NVIDIA_MODEL": "mock-nemotron",
        }
        with patch("agent.__main__.httpx.Client", return_value=model_client):
            with self.assertRaisesRegex(AgentError, "usable read-only tool call"):
                nemotron_lookup(api, "List overdue invoices", env)
        self.assertEqual(self.requests, [])
