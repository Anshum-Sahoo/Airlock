import copy
import json
import unittest
from unittest.mock import Mock

import httpx

from agent.client import TOOLS, AgentError, Airlock, ApiError
from agent.model_demo import WEBHOOK, model_sessions, run_session


def tool(name, arguments, call_id="call_1"):
    return {"tool_calls": [{"type": "function", "id": call_id, "function": {
        "name": name, "arguments": json.dumps(arguments)}}]}


LIST = tool("list_invoices", {"status": "OVERDUE", "limit": 2})
DELETE = tool("bulk_delete_invoices", {"status": "OVERDUE"}, "call_delete")


class ModelDemoTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock(spec=Airlock)
        self.api.create.return_value = {"session_id": "test-session", "baseline_record_count": 500}
        self.sample = {"id": "INV-0001", "status": "OVERDUE", "due_date": "2026-10-10",
                       "notes": "private invoice notes", "customer_name": "private customer"}
        self.list_result = {"total_matching": 420, "returned": 1, "invoices": [self.sample]}
        self.api.execute.side_effect = self.execute
        self.api.complete.side_effect = self.complete
        self.requests = []

    def execute(self, sid, name, args):
        self.assertEqual(sid, "test-session")
        if name == "list_invoices":
            return {"result": self.list_result}
        if name == "get_invoice":
            return {"result": {"invoice": self.sample}}
        if name == "bulk_delete_invoices":
            self.list_result = {"total_matching": 0, "returned": 0, "invoices": []}
            return {"result": {"deleted_count": 420}, "mutations_recorded": 420}
        if name == "stage_webhook":
            error = copy.deepcopy(TOOLS[name]["example_error_responses"][0]["response"]["error"])
            error["details"]["policy_violations"] = error["details"]["policy_violations"][:1]
            raise ApiError(403, error)
        self.fail("Unexpected tool")

    def complete(self, sid, summary):
        hook = self.api.create.call_args.args[1] == "Secret webhook check"
        count = 0 if hook else 420
        return {"agent_summary": summary, "session_id": sid,
                "mutation_counts": {"total": count, "deleted": count},
                "gate_decision": "BLOCK" if hook else "REQUIRE_APPROVAL",
                "policy_violations": [{"policy_id": "POL-003" if hook else "POL-001"}]}

    def run_script(self, replies, scenario="deletion"):
        def handle(request):
            body = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/chat/completions")
            for private in ("private invoice notes", "private customer", "test-agent-token"):
                self.assertNotIn(private, request.content.decode())
            self.requests.append(body)
            reply = replies.pop(0)
            if isinstance(reply, int):
                return httpx.Response(reply)
            return httpx.Response(200, json={"choices": [{"message": reply}]})

        with httpx.Client(base_url="https://model.example/v1",
                          transport=httpx.MockTransport(handle)) as client:
            return run_session(self.api, client, "demo-model", scenario, ["test-agent-token"])

    def test_inspection_and_optional_lookup_feed_next_decision(self):
        manifest = self.run_script([LIST, tool("get_invoice", {"invoice_id": self.sample["id"]}, "detail"),
                                    DELETE, {"content": "420 staged deletions await human review."}])
        self.assertEqual(manifest["gate_decision"], "REQUIRE_APPROVAL")
        self.assertIn("0 overdue invoices remaining", manifest["agent_summary"])
        self.assertIn("get_invoice returned INV-0001", manifest["agent_summary"])
        self.assertIn("420 staged deletions await human review.", manifest["agent_summary"])
        for index, names in enumerate([["list_invoices"], ["get_invoice", "bulk_delete_invoices"],
                                       ["bulk_delete_invoices"]]):
            self.assertEqual([t["function"]["name"] for t in self.requests[index]["tools"]], names)
        self.assertEqual(self.requests[1]["messages"][-1]["tool_call_id"], "call_1")
        self.assertIn("420", self.requests[1]["messages"][-1]["content"])
        self.assertIn(self.sample["due_date"], self.requests[2]["messages"][-1]["content"])
        self.assertNotIn("tools", self.requests[-1])

    def test_webhook_block_is_terminal_and_redacted(self):
        result = self.run_script([tool("stage_webhook", WEBHOOK),
                                  {"content": "Airlock blocked the synthetic webhook."}], "webhook")
        self.api.execute.assert_called_once_with("test-session", "stage_webhook", WEBHOOK)
        self.assertEqual(result["gate_decision"], "BLOCK")
        self.assertIn("POLICY_BLOCK under POL-003", result["agent_summary"])
        self.assertNotIn("sk_live_", json.dumps(self.requests[-1]))

    def test_cross_scenario_lifecycle_and_parallel_calls_never_execute(self):
        invalid = [tool("stage_webhook", WEBHOOK), tool("commit", {}), DELETE,
                   {"tool_calls": LIST["tool_calls"] * 2}, {"content": "done"}]
        for call in invalid:
            with self.subTest(call=call), self.assertRaisesRegex(AgentError, "unavailable tool"):
                self.run_script([call])
        self.api.execute.assert_not_called()

    def test_restrict_webhook_arguments_and_deny_early_mutation(self):
        with self.assertRaisesRegex(AgentError, "fixed synthetic webhook"):
            self.run_script([tool("stage_webhook", {**WEBHOOK, "url": "https://example.org"})], "webhook")
        self.api.execute.assert_not_called()
        with self.assertRaisesRegex(AgentError, "OVERDUE filter"):
            self.run_script([LIST, tool("bulk_delete_invoices", {"status": "PAID"})])
        self.assertEqual(self.api.execute.call_count, 1)
        self.assertIn("of 420", self.api.complete.call_args.args[1])

    def test_seed_mismatch_stops_before_deletion(self):
        self.list_result["total_matching"] = 419
        with self.assertRaisesRegex(AgentError, "420-overdue"):
            self.run_script([LIST])
        self.assertEqual(self.api.execute.call_count, 1)

    def test_timeout_after_submission_is_not_replayed(self):
        self.api.execute.side_effect = [self.execute("test-session", "list_invoices", {}),
                                        AgentError("Outcome may be unknown.")]
        with self.assertRaisesRegex(AgentError, "Inspect session test-session"):
            self.run_script([LIST, DELETE])
        self.assertEqual(self.api.execute.call_count, 2)
        self.api.complete.assert_not_called()

    def test_chat_only_model_supplies_tool_and_summary_failure_keeps_receipts(self):
        def as_text(call):
            func = call["tool_calls"][0]["function"]
            return {"content": json.dumps({"tool_name": func["name"],
                                           "arguments": json.loads(func["arguments"])})}

        result = self.run_script([400, as_text(LIST), as_text(DELETE), 503])
        self.assertEqual(len(self.requests), 4)
        self.assertNotIn("tools", self.requests[1])
        self.assertIn("Model summary unavailable", result["agent_summary"])
        self.assertIn("staged 420 deletions", result["agent_summary"])

    def test_no_credentials_or_unauthorized_model_response(self):
        with self.assertRaisesRegex(AgentError, "NVIDIA_API_KEY"):
            list(model_sessions(self.api, {}))
        self.api.create.assert_not_called()
        with self.assertRaisesRegex(AgentError, "HTTP 401"):
            self.run_script([401])
        self.api.execute.assert_not_called()
        self.assertEqual(len(self.requests), 1)

    def test_summary_cannot_echo_credentials(self):
        result = self.run_script([LIST, DELETE, {"content": "test-agent-token"}])
        self.assertNotIn("test-agent-token", result["agent_summary"])
        self.assertIn("Model summary unavailable", result["agent_summary"])
