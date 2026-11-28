import json
import unittest

import httpx

from agent.client import AgentError
from agent.nemotron import choose_invoice


class RecommendationTests(unittest.TestCase):
    def select(self, proposal):
        candidates = [{"invoice_id": "INV-0042", "amount_cents": 1200,
                       "currency": "USD", "due_date": "2026-01-15"}]

        def respond(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            messages = json.loads(request.content)["messages"]
            self.assertEqual(json.loads(messages[-1]["content"]), candidates)
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(proposal)}}]})

        with httpx.Client(base_url="https://model.example/v1", transport=httpx.MockTransport(respond)) as client:
            return choose_invoice(candidates, client, "test-model")

    def test_valid_note(self):
        proposed = {"invoice_id": "INV-0042", "notes": "Follow up on the outstanding USD 12.00."}
        self.assertEqual(self.select(proposed), proposed)

    def test_rejects_other_invoice_or_field(self):
        for proposal in ({"invoice_id": "INV-0002", "notes": "Review."},
                         {"invoice_id": "INV-0042", "notes": "Review.", "status": "PAID"}):
            with self.subTest(proposal=proposal), self.assertRaises(AgentError):
                self.select(proposal)
